import json

from django.conf import settings

from ..sast_tools import list_directory, read_file, search_codebase
from ..progress import record_scan_event, summarize_tool_result
from .memory import ExplorationResult, ScanMemoryManager


class ScanCancelledError(Exception):
    """Raised when a scan is cancelled while an agent is running."""


class BaseToolCallingAgent:
    def __init__(
        self,
        project,
        scan_job=None,
        provider=None,
        ai_config=None,
        provider_settings=None,
        system_context=None,
        system_context_extra='',
    ):
        self.project = project
        self.scan_job = scan_job
        self.provider = provider
        self.ai_config = ai_config
        self.provider_settings = provider_settings or (
            ai_config.selected_provider_settings() if ai_config else {}
        )
        self.scan_model = self.provider_settings.get('scan_model')
        self.fix_model = self.provider_settings.get('fix_model')
        self.verify_model = self.provider_settings.get('verify_model')
        self.system_context = system_context or self._load_project_context()
        if system_context_extra:
            self.system_context += '\n\n' + system_context_extra
        self.tool_definitions = self._build_tool_definitions()
        self.last_metadata = {}

    def _load_project_context(self):
        context = (
            'You are an expert Application Security Engineer. '
            'You are scanning a repository through tool calling only. '
            'Never assume code exists unless you have found it through the provided tools. '
            'Prefer directory listings, narrow regex searches, and bounded line reads. '
            'Only report exploitable vulnerabilities that are supported by the gathered evidence.'
        )

        for spec_path, heading in (
            ('agents.md', 'Project Specification (agents.md)'),
            ('AGENTS.md', 'Project Specification (AGENTS.md)'),
            ('README.md', 'Project Readme'),
        ):
            try:
                spec = read_file(self.project, spec_path, start_line=1, end_line=120, max_lines=120)
                context += f"\n\n{heading}:\n{spec['content'][:2000]}"
            except Exception:
                pass

        return context

    def _build_tool_definitions(self):
        return [
            {
                'type': 'function',
                'name': 'list_directory',
                'description': 'List files and directories in a workspace-relative directory. Use this first when exploring unfamiliar areas.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'directory': {'type': 'string'},
                    },
                    'required': ['directory'],
                    'additionalProperties': False,
                },
                'strict': True,
            },
            {
                'type': 'function',
                'name': 'search_codebase',
                'description': 'Search the repository with a regex-style query inside a workspace-relative directory.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string'},
                        'directory': {'type': 'string'},
                    },
                    'required': ['query', 'directory'],
                    'additionalProperties': False,
                },
                'strict': True,
            },
            {
                'type': 'function',
                'name': 'read_file',
                'description': 'Read an exact line range from a workspace-relative file.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'filepath': {'type': 'string'},
                        'start_line': {'type': 'integer'},
                        'end_line': {'type': 'integer'},
                    },
                    'required': ['filepath', 'start_line', 'end_line'],
                    'additionalProperties': False,
                },
                'strict': True,
            },
        ]

    def _run_tool_loop(self, task_prompt, model, max_tool_calls=None, progress_phase='scan', progress_title='Agent exploration'):
        max_calls = max_tool_calls or settings.SAST_SCAN_MAX_TOOL_CALLS
        memory = ScanMemoryManager(
            soft_token_threshold=settings.SAST_SCAN_SOFT_CONTEXT_TOKENS,
            hard_token_threshold=settings.SAST_SCAN_HARD_CONTEXT_TOKENS,
        )
        conversation = self.provider.start_conversation(self.system_context, task_prompt)
        stop_reason = 'completed'
        final_response_text = ''

        try:
            self._record_progress(
                progress_phase,
                'phase_started',
                progress_title,
                f'{self.__class__.__name__} started repository exploration.',
                {'model': model, 'max_tool_calls': max_calls},
            )
            while memory.total_calls < max_calls:
                self._ensure_scan_active()
                response = self.provider.create_tool_response(
                    model=model,
                    conversation=conversation,
                    tools=self.tool_definitions,
                )
                if not response.tool_calls:
                    final_response_text = response.output_text
                    self.last_metadata = memory.build_metadata(stop_reason, final_response_text)
                    self._record_progress(
                        progress_phase,
                        'phase_completed',
                        f'{progress_title} completed',
                        'The agent finished its tool exploration phase.',
                        {'tool_call_count': memory.total_calls, 'stop_reason': stop_reason},
                    )
                    return ExplorationResult(
                        final_response_text=final_response_text,
                        stop_reason=stop_reason,
                        memory=memory,
                    )

                tool_results = []
                for function_call in response.tool_calls:
                    self._ensure_scan_active()
                    arguments, argument_error = self._parse_tool_arguments(function_call.arguments)
                    if argument_error:
                        result = argument_error
                    else:
                        result = self._dispatch_tool_call(function_call.name, arguments)
                    memory.record_tool_result(function_call.name, arguments, function_call.call_id, result)
                    self._record_tool_progress(progress_phase, function_call.name, arguments, result, memory.total_calls)
                    tool_results.append((function_call, result))
                    if memory.total_calls >= max_calls:
                        stop_reason = 'tool_budget_exhausted'
                        break

                if tool_results:
                    self.provider.append_tool_results(conversation, tool_results)
                    self._rebase_conversation(conversation, task_prompt, memory)

                if stop_reason == 'tool_budget_exhausted':
                    break
        except ScanCancelledError:
            self.last_metadata = memory.build_metadata('cancelled', final_response_text)
            self._record_progress(
                progress_phase,
                'cancelled',
                f'{progress_title} cancelled',
                'The agent stopped because the scan was cancelled.',
                {'tool_call_count': memory.total_calls},
            )
            raise

        self.last_metadata = memory.build_metadata(stop_reason, final_response_text)
        self._record_progress(
            progress_phase,
            'phase_completed',
            f'{progress_title} stopped',
            f'The tool loop ended with stop reason: {stop_reason}.',
            {'tool_call_count': memory.total_calls, 'stop_reason': stop_reason},
        )
        return ExplorationResult(
            final_response_text=final_response_text,
            stop_reason=stop_reason,
            memory=memory,
        )

    def _parse_tool_arguments(self, raw_arguments):
        raw = raw_arguments or '{}'
        try:
            arguments = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            return {}, self._malformed_tool_arguments_error(exc)
        if not isinstance(arguments, dict):
            return {}, self._malformed_tool_arguments_error('Tool arguments must be a JSON object.')
        return arguments, None

    def _malformed_tool_arguments_error(self, error):
        message = str(error) or error.__class__.__name__
        return {
            'error': f'Malformed tool-call JSON: {message[:300]}',
            'truncated': False,
        }

    def _dispatch_tool_call(self, tool_name, arguments):
        try:
            if tool_name == 'list_directory':
                return list_directory(self.project, arguments.get('directory', ''))
            if tool_name == 'search_codebase':
                return search_codebase(
                    self.project,
                    arguments.get('query', ''),
                    arguments.get('directory', ''),
                )
            if tool_name == 'read_file':
                return read_file(
                    self.project,
                    arguments.get('filepath', ''),
                    start_line=arguments.get('start_line', 1),
                    end_line=arguments.get('end_line', arguments.get('start_line', 1)),
                    max_lines=settings.SAST_SCAN_MAX_READ_LINES,
                    max_bytes=settings.SAST_SCAN_MAX_TOOL_RESULT_BYTES,
                )
        except Exception as exc:
            return {'error': str(exc), 'truncated': False}
        return {'error': f'Unknown tool: {tool_name}', 'truncated': False}

    def _parse_structured_output(self, model, schema, system_prompt, user_prompt):
        return self.provider.parse_structured_output(model, schema, system_prompt, user_prompt)

    def _ensure_scan_active(self):
        if not self.scan_job:
            return
        self.scan_job.refresh_from_db(fields=['status'])
        if self.scan_job.status in ('CANCELLING', 'CANCELLED'):
            raise ScanCancelledError(f'Scan {self.scan_job.id} cancelled.')

    ensure_scan_active = _ensure_scan_active

    def _record_tool_progress(self, phase, tool_name, arguments, result, call_count):
        summary = summarize_tool_result(tool_name, arguments, result)
        detail = self._tool_detail(tool_name, summary)
        self._record_progress(
            phase,
            'tool_call',
            f'Used {tool_name}',
            detail,
            {'tool_call_count': call_count, 'tool': tool_name, **summary},
        )

    def _record_progress(self, phase, event_type, title, detail='', payload=None):
        if not self.scan_job:
            return
        record_scan_event(
            self.scan_job,
            phase=phase,
            event_type=event_type,
            title=title,
            detail=detail,
            payload=payload or {},
        )

    def _tool_detail(self, tool_name, summary):
        if summary.get('error'):
            return f"{tool_name} returned an error: {summary['error']}"
        if tool_name == 'list_directory':
            return f"Listed {summary.get('entry_count', 0)} entries in {summary.get('directory', '.')}"
        if tool_name == 'search_codebase':
            return f"Searched {summary.get('directory', '.')} and found {summary.get('total_hits', 0)} hit(s)"
        if tool_name == 'read_file':
            return (
                f"Read {summary.get('filepath', '')}:"
                f"{summary.get('start_line', 1)}-{summary.get('end_line', summary.get('start_line', 1))}"
            )
        return f'Executed {tool_name}'

    def _rebase_conversation(self, conversation, task_prompt, memory):
        if hasattr(self.provider, 'rebase_conversation'):
            self.provider.rebase_conversation(conversation, self.system_context, task_prompt, memory)
            return

        context_window = memory.build_context_window()
        bounded_memory = (
            'Use this bounded scan memory instead of earlier raw tool outputs. '
            'Do not assume evidence beyond these summaries and excerpts.\n\n'
            f'{context_window}'
        )
        if isinstance(conversation, list):
            conversation[:] = [
                {'role': 'system', 'content': self.system_context},
                {'role': 'user', 'content': task_prompt},
            ]
            if context_window:
                conversation.append({'role': 'user', 'content': bounded_memory})
        elif isinstance(conversation, dict) and 'messages' in conversation:
            conversation['system'] = self.system_context
            conversation['messages'] = [{'role': 'user', 'content': task_prompt}]
            if context_window:
                conversation['messages'].append({'role': 'user', 'content': bounded_memory})
