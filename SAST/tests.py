import os
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .agent import (
    FixResult,
    SASTAgent,
    ScanCancelledError,
    ScanMemoryManager,
    ScanResult,
    VerificationResult,
    Vulnerability,
)
from .agents.memory import aggregate_scan_metadata
from .agents.orchestrator import OrchestratorAgent
from .agents.registry import SpecialistRegistry
from .agents.schemas import OrchestratorSurfaceResult, VulnerabilitySurface
from .agents.specialists import (
    CommandInjectionSpecialistAgent,
    GenericSecuritySpecialistAgent,
)
from .models import Project, SASTFix, SASTScanJob
from .services import ProjectManager
from .sast_tools import list_directory, read_file, search_codebase
from .tasks import run_sast_scan
from .llm import ToolCall, ToolResponse
from .llm.anthropic_provider import AnthropicProvider
from .llm.deepseek_provider import DeepSeekProvider
from .llm.openai_provider import OpenAIProvider


FIXTURE_REPO = Path(__file__).resolve().parent / 'testdata' / 'tool_repo'


class FakeProvider:
    def __init__(self, tool_responses, parse_responses):
        self._tool_responses = list(tool_responses)
        self._parse_responses = list(parse_responses)
        self.create_calls = []
        self.parse_calls = []
        self.appended_tool_results = []

    def start_conversation(self, system_prompt, user_prompt):
        return [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ]

    def create_tool_response(self, model, conversation, tools):
        self.create_calls.append({
            'model': model,
            'conversation': list(conversation),
            'tools': tools,
        })
        return self._tool_responses.pop(0)

    def append_tool_results(self, conversation, tool_results):
        self.appended_tool_results.append(list(tool_results))
        for tool_call, result in tool_results:
            conversation.append({
                'type': 'function_call_output',
                'call_id': tool_call.call_id,
                'output': result,
            })

    def parse_structured_output(self, model, schema, system_prompt, user_prompt):
        self.parse_calls.append({
            'model': model,
            'schema': schema,
            'system_prompt': system_prompt,
            'user_prompt': user_prompt,
        })
        return self._parse_responses.pop(0)


def fake_tool_response(*tool_calls, output_text=''):
    return ToolResponse(output_text=output_text, tool_calls=list(tool_calls))


def fake_tool_call(call_id, name, arguments):
    return ToolCall(call_id=call_id, name=name, arguments=arguments)


class WorkspaceTestCase(TestCase):
    def setUp(self):
        super().setUp()
        temp_root = Path(os.environ.get('SAST_TEST_TEMP_DIR', Path.cwd() / 'media'))
        self.temp_media_path = temp_root / f'test-media-{os.getpid()}-{uuid.uuid4().hex}'
        self.temp_media_path.mkdir(parents=True, exist_ok=True)
        self.media_override = override_settings(MEDIA_ROOT=str(self.temp_media_path))
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.temp_media_path, ignore_errors=True))
        self.env_patcher = mock.patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)

        self.user = User.objects.create_user(username='tester', password='pass12345')
        self.project = Project.objects.create(name='fixture', owner=self.user, status='READY')
        self.manager = ProjectManager(self.project)
        self.workspace = Path(self.manager.prepare_workspace())

    def load_fixture_repo(self):
        shutil.copytree(FIXTURE_REPO, self.workspace, dirs_exist_ok=True)

    def write_file(self, relative_path, content):
        target = self.workspace / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')

    def write_binary(self, relative_path, content):
        target = self.workspace / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


class ToolingTests(WorkspaceTestCase):
    def test_search_codebase_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            search_codebase(self.project, 'dangerous', '../outside')

    def test_search_codebase_scopes_and_ignores_vendor_directories(self):
        self.load_fixture_repo()

        result = search_codebase(self.project, 'shell=True', '')
        returned_paths = {item['path'] for item in result['results']}
        self.assertIn('app/views.py', returned_paths)
        self.assertNotIn('node_modules/ignored.js', returned_paths)

        scoped = search_codebase(self.project, 'dangerous_call', 'app')
        self.assertTrue(all(item['path'].startswith('app/') for item in scoped['results']))

    def test_search_codebase_reports_truncation_and_falls_back_without_ripgrep(self):
        self.load_fixture_repo()
        self.write_file('app/extra.py', 'dangerous_call()\ndangerous_call()\n')

        with self.settings(SAST_SCAN_MAX_SEARCH_RESULTS=1):
            with mock.patch('SAST.sast_tools.shutil.which', return_value=None):
                result = search_codebase(self.project, 'dangerous_call', 'app')

        self.assertTrue(result['truncated'])
        self.assertEqual(len(result['results']), 1)
        self.assertGreaterEqual(result['total_hits'], 2)

    def test_read_file_returns_exact_slice_and_clamps_large_windows(self):
        self.write_file('app/sample.py', 'line1\nline2\nline3\nline4\n')

        result = read_file(
            self.project,
            'app/sample.py',
            start_line=2,
            end_line=10,
            max_lines=2,
        )

        self.assertEqual(result['start_line'], 2)
        self.assertEqual(result['end_line'], 3)
        self.assertEqual(result['content'], 'line2\nline3\n')
        self.assertTrue(result['truncated'])

    def test_read_file_handles_binary_input_without_crashing(self):
        self.write_binary('app/blob.py', b'\xff\xfeunsafe\x00\nsecond-line\n')

        result = read_file(self.project, 'app/blob.py', start_line=1, end_line=2, max_lines=10)

        self.assertIn('unsafe', result['content'])

    def test_list_directory_hides_ignored_directories(self):
        self.load_fixture_repo()

        result = list_directory(self.project, '')

        returned_paths = {entry['path'] for entry in result['entries']}
        self.assertIn('app', returned_paths)
        self.assertNotIn('node_modules', returned_paths)


class MemoryManagerTests(TestCase):
    def test_scan_memory_manager_compacts_and_builds_metadata(self):
        memory = ScanMemoryManager(soft_token_threshold=10, hard_token_threshold=20)

        memory.record_tool_result(
            'search_codebase',
            {'query': 'dangerous', 'directory': ''},
            'call-1',
            {'results': [{'path': 'app/views.py', 'line_number': 10}], 'total_hits': 1, 'truncated': False},
        )
        memory.record_tool_result(
            'read_file',
            {'filepath': 'app/views.py', 'start_line': 1, 'end_line': 50},
            'call-2',
            {'filepath': 'app/views.py', 'start_line': 1, 'end_line': 50, 'content': 'x' * 400, 'truncated': True},
        )

        metadata = memory.build_metadata('completed', 'Potential command injection found.')
        self.assertGreater(memory.compactions, 0)
        self.assertEqual(metadata['tool_call_count'], 2)
        self.assertEqual(metadata['tool_counts']['read_file'], 1)
        self.assertEqual(metadata['truncation_count'], 1)
        self.assertIn('app/views.py', metadata['explored_paths'])
        self.assertIn('Potential command injection found.', metadata['summary'])

    def test_aggregate_scan_metadata_preserves_legacy_top_level_keys(self):
        orchestrator = {
            'summary': 'orchestrator summary',
            'tool_call_count': 2,
            'tool_counts': {'list_directory': 1, 'search_codebase': 1},
            'truncation_count': 0,
            'explored_paths': ['app/views.py'],
            'compactions': 1,
            'stop_reason': 'completed',
        }
        specialist = {
            'surface_id': 'surface-1',
            'vulnerability_type': 'COMMAND_INJECTION',
            'metadata': {
                'summary': 'specialist summary',
                'tool_call_count': 1,
                'tool_counts': {'read_file': 1},
                'truncation_count': 1,
                'explored_paths': ['app/views.py'],
                'compactions': 0,
                'stop_reason': 'completed',
            },
        }

        metadata = aggregate_scan_metadata(orchestrator, [specialist])

        self.assertEqual(metadata['tool_call_count'], 3)
        self.assertEqual(metadata['tool_counts']['read_file'], 1)
        self.assertEqual(metadata['truncation_count'], 1)
        self.assertEqual(metadata['explored_paths'], ['app/views.py'])
        self.assertEqual(metadata['compactions'], 1)
        self.assertEqual(metadata['stop_reason'], 'completed')
        self.assertEqual(metadata['orchestrator'], orchestrator)
        self.assertEqual(metadata['specialists'][0]['surface_id'], 'surface-1')


class ProviderAdapterTests(TestCase):
    def test_openai_tool_conversion_uses_chat_completion_shape(self):
        provider = object.__new__(OpenAIProvider)

        tools = provider._convert_tools([{
            'name': 'read_file',
            'description': 'Read a file',
            'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False},
            'strict': True,
        }])

        self.assertEqual(tools[0]['type'], 'function')
        self.assertEqual(tools[0]['function']['name'], 'read_file')
        self.assertTrue(tools[0]['function']['strict'])

    def test_deepseek_provider_uses_configured_openai_compatible_base_url(self):
        with mock.patch('SAST.llm.openai_provider.OpenAI') as client_cls:
            DeepSeekProvider(
                api_key='test-key',
                base_url='https://api.deepseek.com',
                max_output_tokens=4096,
                request_timeout=120,
            )

        client_cls.assert_called_once_with(
            api_key='test-key',
            timeout=120,
            base_url='https://api.deepseek.com',
        )

    def test_anthropic_tool_results_are_grouped_after_tool_use(self):
        provider = object.__new__(AnthropicProvider)
        conversation = {'system': 'sys', 'messages': [{'role': 'user', 'content': 'scan'}]}

        provider.append_tool_results(conversation, [
            (ToolCall('toolu_1', 'list_directory', '{}'), {'entries': []}),
            (ToolCall('toolu_2', 'read_file', '{}'), {'content': 'x'}),
        ])

        tool_result_message = conversation['messages'][-1]
        self.assertEqual(tool_result_message['role'], 'user')
        self.assertEqual(tool_result_message['content'][0]['type'], 'tool_result')
        self.assertEqual(tool_result_message['content'][0]['tool_use_id'], 'toolu_1')
        self.assertEqual(tool_result_message['content'][1]['tool_use_id'], 'toolu_2')

    def test_structured_output_retries_once_after_invalid_json(self):
        class FakeCompletions:
            def __init__(self):
                self.calls = 0

            def create(self, **kwargs):
                self.calls += 1
                content = 'not json' if self.calls == 1 else '{"findings": []}'
                message = SimpleNamespace(content=content)
                return SimpleNamespace(choices=[SimpleNamespace(message=message)])

        provider = object.__new__(OpenAIProvider)
        provider.max_output_tokens = 4096
        completions = FakeCompletions()
        provider.client = SimpleNamespace(
            chat=SimpleNamespace(completions=completions)
        )

        result = provider.parse_structured_output(
            model='model',
            schema=ScanResult,
            system_prompt='system',
            user_prompt='user',
        )

        self.assertEqual(result.findings, [])
        self.assertEqual(completions.calls, 2)


class AgentLoopTests(WorkspaceTestCase):
    def test_agent_uses_provider_boundary_for_tool_results(self):
        fake_provider = FakeProvider(
            tool_responses=[
                fake_tool_response(fake_tool_call('call-1', 'list_directory', '{"directory":""}')),
                fake_tool_response(output_text='No supported vulnerabilities found.'),
            ],
            parse_responses=[ScanResult(findings=[])],
        )

        with mock.patch('SAST.agent.build_provider', return_value=fake_provider):
            agent = SASTAgent(self.project)
            agent.scan_project()

        self.assertEqual(len(fake_provider.appended_tool_results), 1)
        tool_call, result = fake_provider.appended_tool_results[0][0]
        self.assertEqual(tool_call.name, 'list_directory')
        self.assertIn('entries', result)

    def test_scan_project_uses_tools_and_returns_structured_findings(self):
        self.load_fixture_repo()
        fake_provider = FakeProvider(
            tool_responses=[
                fake_tool_response(fake_tool_call('call-1', 'list_directory', '{"directory":""}')),
                fake_tool_response(fake_tool_call('call-2', 'search_codebase', '{"query":"dangerous_call","directory":"app"}')),
                fake_tool_response(fake_tool_call('call-3', 'read_file', '{"filepath":"app/views.py","start_line":1,"end_line":20}')),
                fake_tool_response(output_text='The request handler executes user-controlled shell commands.'),
            ],
            parse_responses=[
                ScanResult(findings=[
                    Vulnerability(
                        file_path='app/views.py',
                        line_number=9,
                        severity='HIGH',
                        title='Command Injection',
                        description='User-controlled shell command execution.',
                        code_snippet='subprocess.run(user_cmd, shell=True, capture_output=True, text=True)',
                        confidence_score=0.97,
                        ai_explanation='The handler passes attacker-controlled input to a shell.',
                    )
                ])
            ],
        )

        with mock.patch('SAST.agent.build_provider', return_value=fake_provider):
            agent = SASTAgent(self.project)
            findings = agent.scan_project()

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['file_path'], 'app/views.py')
        self.assertEqual(agent.last_scan_metadata['tool_call_count'], 3)
        second_conversation = fake_provider.create_calls[1]['conversation']
        self.assertTrue(any(item.get('type') == 'function_call_output' for item in second_conversation if isinstance(item, dict)))

    def test_scan_project_does_not_inline_large_files_in_initial_prompt(self):
        self.write_file('large_module.py', ('SENTINEL_BLOCK\n' * 5000))
        fake_provider = FakeProvider(
            tool_responses=[fake_tool_response(output_text='No supported vulnerabilities found.')],
            parse_responses=[ScanResult(findings=[])],
        )

        with mock.patch('SAST.agent.build_provider', return_value=fake_provider):
            agent = SASTAgent(self.project)
            agent.scan_project()

        initial_input = str(fake_provider.create_calls[0]['conversation'])
        self.assertNotIn('SENTINEL_BLOCK', initial_input)

    def test_scan_project_respects_cancellation_between_tool_turns(self):
        self.load_fixture_repo()
        scan_job = SASTScanJob.objects.create(project=self.project, status='SCANNING')
        fake_provider = FakeProvider(
            tool_responses=[
                fake_tool_response(fake_tool_call('call-1', 'list_directory', '{"directory":""}')),
            ],
            parse_responses=[],
        )

        def cancel_after_first_tool(project, directory):
            scan_job.status = 'CANCELLED'
            scan_job.save(update_fields=['status'])
            return {'directory': directory, 'entries': [], 'truncated': False}

        with mock.patch('SAST.agent.build_provider', return_value=fake_provider):
            with mock.patch('SAST.agents.base.list_directory', side_effect=cancel_after_first_tool):
                agent = SASTAgent(self.project, scan_job=scan_job)
                with self.assertRaises(ScanCancelledError):
                    agent.scan_project()


class MultiAgentPipelineTests(WorkspaceTestCase):
    def provider_settings(self):
        return {
            'scan_model': 'scan-model',
            'fix_model': 'fix-model',
            'verify_model': 'verify-model',
        }

    def surface(self, vulnerability_type='COMMAND_INJECTION'):
        return VulnerabilitySurface(
            surface_id='surface-1',
            vulnerability_type=vulnerability_type,
            title='Possible command injection',
            rationale='Request input appears to reach subprocess usage.',
            evidence_paths=['app/views.py'],
            recommended_files=['app/views.py'],
            priority='HIGH',
        )

    def vulnerability(self):
        return Vulnerability(
            file_path='app/views.py',
            line_number=9,
            severity='HIGH',
            title='Command Injection',
            description='User-controlled shell command execution.',
            code_snippet='subprocess.run(user_cmd, shell=True, capture_output=True, text=True)',
            confidence_score=0.97,
            ai_explanation='The handler passes attacker-controlled input to a shell.',
        )

    def fix(self):
        return FixResult(
            scope='SNIPPET',
            start_line=8,
            end_line=9,
            fixed_code='safe_cmd = [user_cmd]\nreturn subprocess.run(safe_cmd, shell=False, capture_output=True, text=True)',
            explanation='Execute the command without invoking a shell.',
        )

    def verification(self):
        return VerificationResult(
            is_true_positive=True,
            reasoning='The proposed fix removes shell interpretation and preserves the handler flow.',
        )

    def test_registry_dispatches_known_types_and_unknown_falls_back(self):
        registry = SpecialistRegistry()

        self.assertIs(registry.get_specialist_class('COMMAND_INJECTION'), CommandInjectionSpecialistAgent)
        self.assertIs(registry.get_specialist_class('unexpected'), GenericSecuritySpecialistAgent)

    def test_orchestrator_discovers_surfaces_without_direct_findings(self):
        fake_provider = FakeProvider(
            tool_responses=[
                fake_tool_response(fake_tool_call('orch-1', 'list_directory', '{"directory":""}')),
                fake_tool_response(output_text='Potential subprocess surface in app/views.py.'),
            ],
            parse_responses=[
                OrchestratorSurfaceResult(surfaces=[self.surface()]),
            ],
        )

        agent = OrchestratorAgent(
            self.project,
            provider=fake_provider,
            provider_settings=self.provider_settings(),
        )
        surfaces = agent.discover_surfaces()

        self.assertEqual(len(surfaces), 1)
        self.assertEqual(surfaces[0].vulnerability_type, 'COMMAND_INJECTION')
        self.assertIs(fake_provider.parse_calls[0]['schema'], OrchestratorSurfaceResult)
        self.assertEqual(agent.last_metadata['tool_call_count'], 1)

    def test_specialist_investigates_generates_fix_and_verifies(self):
        self.load_fixture_repo()
        fake_provider = FakeProvider(
            tool_responses=[
                fake_tool_response(fake_tool_call('spec-1', 'read_file', '{"filepath":"app/views.py","start_line":1,"end_line":20}')),
                fake_tool_response(output_text='Confirmed user input reaches shell=True subprocess.'),
                fake_tool_response(fake_tool_call('fix-1', 'read_file', '{"filepath":"app/views.py","start_line":6,"end_line":12}')),
                fake_tool_response(output_text='A snippet-scoped fix is sufficient.'),
                fake_tool_response(fake_tool_call('verify-1', 'read_file', '{"filepath":"app/views.py","start_line":6,"end_line":12}')),
                fake_tool_response(output_text='The fix removes shell execution.'),
            ],
            parse_responses=[
                ScanResult(findings=[self.vulnerability()]),
                self.fix(),
                self.verification(),
            ],
        )
        specialist = CommandInjectionSpecialistAgent(
            self.project,
            provider=fake_provider,
            provider_settings=self.provider_settings(),
        )

        results = specialist.run(self.surface())

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].surface_id, 'surface-1')
        self.assertEqual(results[0].fix.scope, 'SNIPPET')
        self.assertTrue(results[0].verification.is_true_positive)
        self.assertEqual(results[0].specialist_metadata['tool_call_count'], 3)
        self.assertEqual(len(results[0].specialist_metadata['phases']), 3)


class RunSastScanTaskTests(WorkspaceTestCase):
    def surface(self):
        return VulnerabilitySurface(
            surface_id='surface-1',
            vulnerability_type='COMMAND_INJECTION',
            title='Possible command injection',
            rationale='Request input appears to reach subprocess usage.',
            evidence_paths=['app/views.py'],
            recommended_files=['app/views.py'],
            priority='HIGH',
        )

    def vulnerability(self):
        return Vulnerability(
            file_path='app/views.py',
            line_number=9,
            severity='HIGH',
            title='Command Injection',
            description='User-controlled shell command execution.',
            code_snippet='subprocess.run(user_cmd, shell=True, capture_output=True, text=True)',
            confidence_score=0.97,
            ai_explanation='The handler passes attacker-controlled input to a shell.',
        )

    def fix(self):
        return FixResult(
            scope='SNIPPET',
            start_line=8,
            end_line=9,
            fixed_code='safe_cmd = [user_cmd]\nreturn subprocess.run(safe_cmd, shell=False, capture_output=True, text=True)',
            explanation='Execute the command without invoking a shell.',
        )

    def verification(self):
        return VerificationResult(
            is_true_positive=True,
            reasoning='The proposed fix removes shell interpretation and preserves the handler flow.',
        )

    def test_run_sast_scan_routes_all_ai_calls_through_provider(self):
        self.load_fixture_repo()
        scan_job = SASTScanJob.objects.create(project=self.project, status='PENDING')
        fake_provider = FakeProvider(
            tool_responses=[
                fake_tool_response(fake_tool_call('orch-1', 'list_directory', '{"directory":""}')),
                fake_tool_response(fake_tool_call('orch-2', 'search_codebase', '{"query":"subprocess.run","directory":"app"}')),
                fake_tool_response(output_text='Potential subprocess surface in app/views.py.'),
                fake_tool_response(fake_tool_call('spec-1', 'read_file', '{"filepath":"app/views.py","start_line":1,"end_line":20}')),
                fake_tool_response(output_text='Confirmed user input reaches shell=True subprocess.'),
                fake_tool_response(fake_tool_call('fix-1', 'read_file', '{"filepath":"app/views.py","start_line":6,"end_line":12}')),
                fake_tool_response(output_text='A snippet-scoped fix is sufficient.'),
                fake_tool_response(fake_tool_call('verify-1', 'read_file', '{"filepath":"app/views.py","start_line":6,"end_line":12}')),
                fake_tool_response(output_text='The fix removes shell execution and remains syntactically safe.'),
            ],
            parse_responses=[
                OrchestratorSurfaceResult(surfaces=[self.surface()]),
                ScanResult(findings=[self.vulnerability()]),
                self.fix(),
                self.verification(),
            ],
        )

        with mock.patch('SAST.agents.orchestrator.build_provider', return_value=fake_provider):
            result = run_sast_scan(scan_job.id)

        scan_job.refresh_from_db()
        self.assertEqual(scan_job.status, 'COMPLETED')
        self.assertIn('completed', result.lower())
        self.assertEqual(len(fake_provider.parse_calls), 4)
        self.assertEqual(len(fake_provider.appended_tool_results), 5)
        self.assertEqual(fake_provider.create_calls[0]['model'], 'gpt-5-nano')

    def test_run_sast_scan_persists_snippet_fix_fields_and_metadata(self):
        self.load_fixture_repo()
        scan_job = SASTScanJob.objects.create(project=self.project, status='PENDING')
        fake_provider = FakeProvider(
            tool_responses=[
                fake_tool_response(fake_tool_call('orch-1', 'list_directory', '{"directory":""}')),
                fake_tool_response(fake_tool_call('orch-2', 'search_codebase', '{"query":"subprocess.run","directory":"app"}')),
                fake_tool_response(output_text='Potential subprocess surface in app/views.py.'),
                fake_tool_response(fake_tool_call('spec-1', 'read_file', '{"filepath":"app/views.py","start_line":1,"end_line":20}')),
                fake_tool_response(output_text='Confirmed user input reaches shell=True subprocess.'),
                fake_tool_response(fake_tool_call('fix-1', 'read_file', '{"filepath":"app/views.py","start_line":6,"end_line":12}')),
                fake_tool_response(output_text='A snippet-scoped fix is sufficient.'),
                fake_tool_response(fake_tool_call('verify-1', 'read_file', '{"filepath":"app/views.py","start_line":6,"end_line":12}')),
                fake_tool_response(output_text='The fix removes shell execution and remains syntactically safe.'),
            ],
            parse_responses=[
                OrchestratorSurfaceResult(surfaces=[self.surface()]),
                ScanResult(findings=[self.vulnerability()]),
                self.fix(),
                self.verification(),
            ],
        )

        with mock.patch('SAST.agents.orchestrator.build_provider', return_value=fake_provider):
            result = run_sast_scan(scan_job.id)

        scan_job.refresh_from_db()
        self.assertEqual(scan_job.status, 'COMPLETED')
        self.assertIn('completed', result.lower())
        self.assertEqual(scan_job.agent_run_metadata['tool_call_count'], 5)
        self.assertIn('orchestrator', scan_job.agent_run_metadata)
        self.assertEqual(scan_job.agent_run_metadata['specialists'][0]['surface_id'], 'surface-1')
        self.assertEqual(scan_job.findings.count(), 1)

        fix = SASTFix.objects.get()
        self.assertEqual(fix.scope, 'SNIPPET')
        self.assertEqual(fix.start_line, 8)
        self.assertEqual(fix.end_line, 9)

    def test_run_sast_scan_records_missing_provider_key(self):
        self.load_fixture_repo()
        scan_job = SASTScanJob.objects.create(project=self.project, status='PENDING')

        with mock.patch.dict(os.environ, {}, clear=True):
            result = run_sast_scan(scan_job.id)

        scan_job.refresh_from_db()
        self.assertEqual(scan_job.status, 'FAILED')
        self.assertIn('OPENAI_API_KEY', result)
        self.assertEqual(scan_job.agent_run_metadata['stop_reason'], 'provider_initialization_failed')
        self.assertIn('OPENAI_API_KEY', scan_job.agent_run_metadata['error'])

    def test_run_sast_scan_records_cancellation_during_orchestrator(self):
        self.load_fixture_repo()
        scan_job = SASTScanJob.objects.create(project=self.project, status='PENDING')
        fake_provider = FakeProvider(
            tool_responses=[
                fake_tool_response(fake_tool_call('orch-1', 'list_directory', '{"directory":""}')),
            ],
            parse_responses=[],
        )

        def cancel_after_tool(project, directory):
            scan_job.status = 'CANCELLED'
            scan_job.save(update_fields=['status'])
            return {'directory': directory, 'entries': [], 'truncated': False}

        with mock.patch('SAST.agents.orchestrator.build_provider', return_value=fake_provider):
            with mock.patch('SAST.agents.base.list_directory', side_effect=cancel_after_tool):
                result = run_sast_scan(scan_job.id)

        scan_job.refresh_from_db()
        self.assertEqual(scan_job.status, 'CANCELLED')
        self.assertIn('cancelled', result.lower())
        self.assertEqual(scan_job.agent_run_metadata['stop_reason'], 'cancelled')
        self.assertEqual(scan_job.agent_run_metadata['tool_call_count'], 1)

    def test_run_sast_scan_records_cancellation_during_specialist(self):
        self.load_fixture_repo()
        scan_job = SASTScanJob.objects.create(project=self.project, status='PENDING')
        fake_provider = FakeProvider(
            tool_responses=[
                fake_tool_response(output_text='Potential subprocess surface in app/views.py.'),
                fake_tool_response(fake_tool_call('spec-1', 'read_file', '{"filepath":"app/views.py","start_line":1,"end_line":20}')),
            ],
            parse_responses=[
                OrchestratorSurfaceResult(surfaces=[self.surface()]),
            ],
        )

        def cancel_after_read(project, file_path, start_line=1, end_line=None, max_lines=None, max_bytes=None):
            if file_path == 'app/views.py':
                scan_job.status = 'CANCELLED'
                scan_job.save(update_fields=['status'])
            return {
                'filepath': file_path,
                'start_line': start_line,
                'end_line': end_line,
                'total_lines': 20,
                'content': '',
                'truncated': False,
            }

        with mock.patch('SAST.agents.orchestrator.build_provider', return_value=fake_provider):
            with mock.patch('SAST.agents.base.read_file', side_effect=cancel_after_read):
                result = run_sast_scan(scan_job.id)

        scan_job.refresh_from_db()
        self.assertEqual(scan_job.status, 'CANCELLED')
        self.assertIn('cancelled', result.lower())
        self.assertEqual(scan_job.agent_run_metadata['stop_reason'], 'cancelled')
        self.assertEqual(scan_job.agent_run_metadata['specialists'][0]['surface_id'], 'surface-1')
