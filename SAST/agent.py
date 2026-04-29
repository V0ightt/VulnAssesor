import json
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional

from django.conf import settings
from Dashboard.models import AIConfig
from pydantic import BaseModel, Field
from .llm import build_provider
from .sast_tools import list_directory, read_file, search_codebase

# --- Structured Outputs (Pydantic) ---
class Vulnerability(BaseModel):
    file_path: str
    line_number: int
    end_line: Optional[int] = None
    severity: str = Field(..., pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    title: str
    description: str
    code_snippet: str
    confidence_score: float
    ai_explanation: str

class ScanResult(BaseModel):
    findings: List[Vulnerability]

class FixResult(BaseModel):
    scope: str = Field(..., pattern="^(SNIPPET|FILE)$")
    start_line: int
    end_line: int
    fixed_code: str
    explanation: str

class VerificationResult(BaseModel):
    is_true_positive: bool
    reasoning: str


class ScanCancelledError(Exception):
    """Raised when a scan is cancelled while the agent is running."""


@dataclass
class MemoryEvent:
    input_item: dict
    summary_line: str
    token_estimate: int


class ScanMemoryManager:
    def __init__(self, soft_token_threshold, hard_token_threshold):
        self.soft_token_threshold = soft_token_threshold
        self.hard_token_threshold = hard_token_threshold
        self.summary_lines = []
        self.recent_events = []
        self.tool_counts = Counter()
        self.truncation_count = 0
        self.explored_paths = set()
        self.compactions = 0
        self.total_calls = 0

    def record_tool_result(self, tool_name, arguments, call_id, result):
        result_payload = result if isinstance(result, dict) else {'value': result}
        output_text = json.dumps(result_payload, ensure_ascii=True)
        output_item = {
            'type': 'function_call_output',
            'call_id': call_id,
            'output': output_text,
        }
        event = MemoryEvent(
            input_item=output_item,
            summary_line=self._build_summary_line(tool_name, arguments, result_payload),
            token_estimate=max(1, len(output_text) // 4),
        )
        self.total_calls += 1
        self.tool_counts[tool_name] += 1
        if result_payload.get('truncated'):
            self.truncation_count += 1
        self._capture_paths(result_payload)
        self.recent_events.append(event)
        self._compact_if_needed()
        return output_item

    def build_input_items(self):
        items = []
        if self.summary_lines:
            items.append({
                'role': 'user',
                'content': "Summary of earlier tool results:\n" + "\n".join(f"- {line}" for line in self.summary_lines[-20:]),
            })
        items.extend(event.input_item for event in self.recent_events)
        return items

    def build_investigation_summary(self, final_response_text=''):
        chunks = []
        if self.summary_lines:
            chunks.append("Earlier exploration summary:\n" + "\n".join(f"- {line}" for line in self.summary_lines[-20:]))
        if self.recent_events:
            recent_text = "\n".join(
                f"- {event.summary_line}" for event in self.recent_events[-10:]
            )
            chunks.append("Recent tool results:\n" + recent_text)
        if final_response_text:
            chunks.append("Model investigation summary:\n" + final_response_text.strip())
        return "\n\n".join(chunk for chunk in chunks if chunk).strip()

    def build_metadata(self, stop_reason, final_response_text=''):
        return {
            'summary': self.build_investigation_summary(final_response_text),
            'tool_call_count': self.total_calls,
            'tool_counts': dict(self.tool_counts),
            'truncation_count': self.truncation_count,
            'explored_paths': sorted(self.explored_paths),
            'compactions': self.compactions,
            'stop_reason': stop_reason,
        }

    def _build_summary_line(self, tool_name, arguments, result_payload):
        if tool_name == 'list_directory':
            directory = arguments.get('directory', '') or '.'
            entries = result_payload.get('entries', [])
            sample = ', '.join(entry.get('path', entry.get('name', '')) for entry in entries[:5]) or 'no entries'
            return f"Listed {directory}: {sample}"
        if tool_name == 'search_codebase':
            query = arguments.get('query', '')
            results = result_payload.get('results', [])
            sample = ', '.join(f"{item.get('path')}:{item.get('line_number')}" for item in results[:5]) or 'no matches'
            return f"Searched for `{query}` and found {result_payload.get('total_hits', 0)} hits ({sample})"
        if tool_name == 'read_file':
            filepath = arguments.get('filepath', '')
            start_line = result_payload.get('start_line', arguments.get('start_line', 1))
            end_line = result_payload.get('end_line', arguments.get('end_line', start_line))
            return f"Read {filepath}:{start_line}-{end_line}"
        return f"Used {tool_name}"

    def _capture_paths(self, result_payload):
        for entry in result_payload.get('entries', []):
            path = entry.get('path')
            if path:
                self.explored_paths.add(path)
        for entry in result_payload.get('results', []):
            path = entry.get('path')
            if path:
                self.explored_paths.add(path)
        filepath = result_payload.get('filepath')
        if filepath:
            self.explored_paths.add(filepath)

    def _compact_if_needed(self):
        while self._estimated_recent_tokens() > self.soft_token_threshold and len(self.recent_events) > 1:
            event = self.recent_events.pop(0)
            self.summary_lines.append(event.summary_line)
            self.compactions += 1

        if self._estimated_recent_tokens() > self.hard_token_threshold and self.recent_events:
            event = self.recent_events.pop(0)
            self.summary_lines.append(event.summary_line)
            self.compactions += 1

    def _estimated_recent_tokens(self):
        return sum(event.token_estimate for event in self.recent_events)


@dataclass
class ExplorationResult:
    final_response_text: str
    stop_reason: str
    memory: ScanMemoryManager

class SASTAgent:
    def __init__(self, project, scan_job=None):
        self.ai_config = AIConfig.get_config()
        self.provider = build_provider(self.ai_config)
        self.project = project
        self.scan_job = scan_job
        self.system_context = self._load_project_context()
        self.last_scan_metadata = {}
        self.tool_definitions = self._build_tool_definitions()
        provider_settings = self.ai_config.selected_provider_settings()
        self.scan_model = provider_settings['scan_model']
        self.fix_model = provider_settings['fix_model']
        self.verify_model = provider_settings['verify_model']

    def _load_project_context(self):
        """
        Reads agents.md and README.md from the TARGET PROJECT to build the System Prompt.
        """
        context = (
            "You are an expert Application Security Engineer. "
            "You are scanning a repository through tool calling only. "
            "Never assume code exists unless you have found it through the provided tools. "
            "Prefer directory listings, narrow regex searches, and bounded line reads. "
            "Only report exploitable vulnerabilities that are supported by the gathered evidence."
        )
        
        # Try to read agents.md
        try:
            agents_md = read_file(self.project, 'agents.md', start_line=1, end_line=120, max_lines=120)
            context += f"\n\nProject Specification (agents.md):\n{agents_md['content'][:2000]}"
        except Exception:
            pass
             
        # Try to read README.md
        try:
            readme_md = read_file(self.project, 'README.md', start_line=1, end_line=120, max_lines=120)
            context += f"\n\nProject Readme:\n{readme_md['content'][:2000]}"
        except Exception:
            pass
             
        return context

    def scan_project(self):
        exploration = self._run_tool_loop(
            task_prompt=(
                "Inspect this repository for exploitable vulnerabilities. "
                "Start from the repository root, map likely entrypoints and trust boundaries, then "
                "search for request handlers, auth flows, file uploads, subprocess usage, template rendering, "
                "deserialization, secrets, and dangerous sinks. Use tools only. "
                "When you have enough evidence, stop calling tools and summarize the vulnerabilities you found."
            ),
            model=self.scan_model,
        )
        self.last_scan_metadata = exploration.memory.build_metadata(exploration.stop_reason, exploration.final_response_text)
        parsed = self._parse_structured_output(
            model=self.scan_model,
            schema=ScanResult,
            system_prompt=(
                self.system_context
                + "\n\nConvert the investigation transcript into structured vulnerability findings. "
                "Only include issues directly supported by the gathered evidence. "
                "If no supported vulnerability exists, return an empty findings list."
            ),
            user_prompt=exploration.memory.build_investigation_summary(exploration.final_response_text),
        )
        findings = [finding.model_dump() for finding in parsed.findings]
        return findings

    def verify_fix(self, finding, fix_data):
        """Verifies if a fix resolves the issue using bounded repository context."""
        line_end = finding.get('end_line') or finding['line_number']
        exploration = self._run_tool_loop(
            task_prompt=(
                f"Verify whether the proposed fix for '{finding['title']}' in {finding['file_path']} "
                f"at lines {finding['line_number']}-{line_end} resolves the issue without introducing "
                "new security bugs or obvious syntax problems. Use repository tools to inspect only the "
                "necessary context.\n\n"
                f"Finding details:\n{json.dumps(finding, ensure_ascii=True)}\n\n"
                f"Proposed fix:\n{json.dumps(fix_data, ensure_ascii=True)}"
            ),
            model=self.verify_model,
            max_tool_calls=max(6, settings.SAST_SCAN_MAX_TOOL_CALLS // 2),
        )
        result = self._parse_structured_output(
            model=self.verify_model,
            schema=VerificationResult,
            system_prompt="You are a QA engineer verifying AI-generated security fixes. Return structured verification only.",
            user_prompt=exploration.memory.build_investigation_summary(exploration.final_response_text),
        )
        return {
            "verified": result.is_true_positive,
            "reason": result.reasoning,
        }

    def generate_fix(self, finding):
        """Generates a fix for a finding using bounded repository context."""
        line_end = finding.get('end_line') or finding['line_number']
        exploration = self._run_tool_loop(
            task_prompt=(
                f"Generate a secure fix for '{finding['title']}' in {finding['file_path']} "
                f"at lines {finding['line_number']}-{line_end}. "
                "Use repository tools to inspect the vulnerable region and nearby code. "
                "Prefer a snippet-scoped fix. Use FILE scope only if you have read and need to replace the entire file.\n\n"
                f"Finding details:\n{json.dumps(finding, ensure_ascii=True)}"
            ),
            model=self.fix_model,
            max_tool_calls=max(6, settings.SAST_SCAN_MAX_TOOL_CALLS // 2),
        )
        result = self._parse_structured_output(
            model=self.fix_model,
            schema=FixResult,
            system_prompt=(
                self.system_context
                + "\n\nReturn a structured fix. `scope` must be SNIPPET or FILE. "
                "Use precise start_line and end_line values for the replacement range."
            ),
            user_prompt=exploration.memory.build_investigation_summary(exploration.final_response_text),
        )
        return result.model_dump()

    def _build_tool_definitions(self):
        return [
            {
                "type": "function",
                "name": "list_directory",
                "description": "List files and directories in a workspace-relative directory. Use this first when exploring unfamiliar areas.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string"},
                    },
                    "required": ["directory"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "search_codebase",
                "description": "Search the repository with a regex-style query inside a workspace-relative directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "directory": {"type": "string"},
                    },
                    "required": ["query", "directory"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "read_file",
                "description": "Read an exact line range from a workspace-relative file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filepath": {"type": "string"},
                        "start_line": {"type": "integer"},
                        "end_line": {"type": "integer"},
                    },
                    "required": ["filepath", "start_line", "end_line"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        ]

    def _run_tool_loop(self, task_prompt, model, max_tool_calls=None):
        max_calls = max_tool_calls or settings.SAST_SCAN_MAX_TOOL_CALLS
        memory = ScanMemoryManager(
            soft_token_threshold=settings.SAST_SCAN_SOFT_CONTEXT_TOKENS,
            hard_token_threshold=settings.SAST_SCAN_HARD_CONTEXT_TOKENS,
        )
        conversation = self.provider.start_conversation(self.system_context, task_prompt)
        stop_reason = 'completed'
        final_response_text = ''

        while memory.total_calls < max_calls:
            self._ensure_scan_active()
            response = self.provider.create_tool_response(
                model=model,
                conversation=conversation,
                tools=self.tool_definitions,
            )
            if not response.tool_calls:
                final_response_text = response.output_text
                return ExplorationResult(
                    final_response_text=final_response_text,
                    stop_reason=stop_reason,
                    memory=memory,
                )

            tool_results = []
            for function_call in response.tool_calls:
                self._ensure_scan_active()
                arguments = json.loads(function_call.arguments or '{}')
                result = self._dispatch_tool_call(function_call.name, arguments)
                memory.record_tool_result(function_call.name, arguments, function_call.call_id, result)
                tool_results.append((function_call, result))
                if memory.total_calls >= max_calls:
                    stop_reason = 'tool_budget_exhausted'
                    break

            if tool_results:
                self.provider.append_tool_results(conversation, tool_results)

            if stop_reason == 'tool_budget_exhausted':
                break

        return ExplorationResult(
            final_response_text=final_response_text,
            stop_reason=stop_reason,
            memory=memory,
        )

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
        if self.scan_job.status == 'CANCELLED':
            raise ScanCancelledError(f"Scan {self.scan_job.id} cancelled.")
