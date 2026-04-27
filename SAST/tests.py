import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
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
from .models import Project, SASTFix, SASTScanJob
from .services import ProjectManager
from .sast_tools import list_directory, read_file, search_codebase
from .tasks import run_sast_scan


FIXTURE_REPO = Path(__file__).resolve().parent / 'testdata' / 'tool_repo'


class FakeFunctionCall:
    def __init__(self, call_id, name, arguments):
        self.type = 'function_call'
        self.call_id = call_id
        self.name = name
        self.arguments = arguments


class FakeFunctionCallWithStatus(FakeFunctionCall):
    def __init__(self, call_id, name, arguments, status='completed', index=0):
        super().__init__(call_id, name, arguments)
        self.status = status
        self.index = index


class FakeDumpableResponseItem:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self, mode='json'):
        return dict(self._payload)


class FakeResponse:
    def __init__(self, output=None, output_text=''):
        self.output = output or []
        self.output_text = output_text


class FakeResponsesAPI:
    def __init__(self, create_responses, parse_responses):
        self._create_responses = list(create_responses)
        self._parse_responses = list(parse_responses)
        self.create_calls = []
        self.parse_calls = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return self._create_responses.pop(0)

    def parse(self, **kwargs):
        self.parse_calls.append(kwargs)
        return SimpleNamespace(output_parsed=self._parse_responses.pop(0))


class FakeOpenAIClient:
    def __init__(self, create_responses, parse_responses):
        self.responses = FakeResponsesAPI(create_responses, parse_responses)


class WorkspaceTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.temp_media = TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.temp_media.cleanup)
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


class AgentLoopTests(WorkspaceTestCase):
    def test_serialize_response_items_strips_unsupported_fields(self):
        fake_client = FakeOpenAIClient(create_responses=[], parse_responses=[])
        with mock.patch('SAST.agent.OpenAI', return_value=fake_client):
            agent = SASTAgent(self.project)

        serialized = agent._serialize_response_items([
            {
                'type': 'message',
                'role': 'assistant',
                'content': [{'type': 'output_text', 'text': 'hello'}],
                'status': 'completed',
                'index': 0,
            },
            FakeFunctionCallWithStatus('call-1', 'read_file', '{"filepath":"app/views.py"}', index=1),
            FakeDumpableResponseItem({
                'type': 'function_call',
                'id': 'fc_1',
                'name': 'search_codebase',
                'arguments': '{"query":"dangerous"}',
                'status': 'in_progress',
                'metadata': {'provider': 'test'},
            }),
        ])

        self.assertEqual(len(serialized), 1)
        self.assertEqual(serialized[0]['type'], 'function_call')
        for item in serialized:
            self.assertNotIn('status', item)
            self.assertNotIn('index', item)
            self.assertNotIn('metadata', item)

    def test_scan_project_uses_tools_and_returns_structured_findings(self):
        self.load_fixture_repo()
        fake_client = FakeOpenAIClient(
            create_responses=[
                FakeResponse(output=[FakeFunctionCall('call-1', 'list_directory', '{"directory":""}')]),
                FakeResponse(output=[FakeFunctionCall('call-2', 'search_codebase', '{"query":"dangerous_call","directory":"app"}')]),
                FakeResponse(output=[FakeFunctionCall('call-3', 'read_file', '{"filepath":"app/views.py","start_line":1,"end_line":20}')]),
                FakeResponse(output_text='The request handler executes user-controlled shell commands.'),
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

        with mock.patch('SAST.agent.OpenAI', return_value=fake_client):
            agent = SASTAgent(self.project)
            findings = agent.scan_project()

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['file_path'], 'app/views.py')
        self.assertEqual(agent.last_scan_metadata['tool_call_count'], 3)
        second_call_inputs = fake_client.responses.create_calls[1]['input']
        self.assertTrue(any(item.get('type') == 'function_call' for item in second_call_inputs if isinstance(item, dict)))
        self.assertTrue(any(item.get('type') == 'function_call_output' for item in second_call_inputs if isinstance(item, dict)))

    def test_scan_project_does_not_inline_large_files_in_initial_prompt(self):
        self.write_file('large_module.py', ('SENTINEL_BLOCK\n' * 5000))
        fake_client = FakeOpenAIClient(
            create_responses=[FakeResponse(output_text='No supported vulnerabilities found.')],
            parse_responses=[ScanResult(findings=[])],
        )

        with mock.patch('SAST.agent.OpenAI', return_value=fake_client):
            agent = SASTAgent(self.project)
            agent.scan_project()

        initial_input = str(fake_client.responses.create_calls[0]['input'])
        self.assertNotIn('SENTINEL_BLOCK', initial_input)

    def test_scan_project_respects_cancellation_between_tool_turns(self):
        self.load_fixture_repo()
        scan_job = SASTScanJob.objects.create(project=self.project, status='SCANNING')
        fake_client = FakeOpenAIClient(
            create_responses=[
                FakeResponse(output=[FakeFunctionCall('call-1', 'list_directory', '{"directory":""}')]),
            ],
            parse_responses=[],
        )

        def cancel_after_first_tool(project, directory):
            scan_job.status = 'CANCELLED'
            scan_job.save(update_fields=['status'])
            return {'directory': directory, 'entries': [], 'truncated': False}

        with mock.patch('SAST.agent.OpenAI', return_value=fake_client):
            with mock.patch('SAST.agent.list_directory', side_effect=cancel_after_first_tool):
                agent = SASTAgent(self.project, scan_job=scan_job)
                with self.assertRaises(ScanCancelledError):
                    agent.scan_project()


class RunSastScanTaskTests(WorkspaceTestCase):
    def test_run_sast_scan_replay_inputs_strip_unsupported_fields(self):
        self.load_fixture_repo()
        scan_job = SASTScanJob.objects.create(project=self.project, status='PENDING')
        fake_client = FakeOpenAIClient(
            create_responses=[
                FakeResponse(output=[FakeFunctionCallWithStatus('scan-1', 'list_directory', '{"directory":""}', index=0)]),
                FakeResponse(output=[FakeFunctionCallWithStatus('scan-2', 'search_codebase', '{"query":"subprocess.run","directory":"app"}', index=1)]),
                FakeResponse(output=[FakeFunctionCallWithStatus('scan-3', 'read_file', '{"filepath":"app/views.py","start_line":1,"end_line":20}', index=2)]),
                FakeResponse(output_text='The app uses user input in a shell command.'),
                FakeResponse(output=[FakeFunctionCallWithStatus('fix-1', 'read_file', '{"filepath":"app/views.py","start_line":6,"end_line":12}', index=3)]),
                FakeResponse(output_text='A snippet-scoped fix is sufficient.'),
                FakeResponse(output=[FakeFunctionCallWithStatus('verify-1', 'read_file', '{"filepath":"app/views.py","start_line":6,"end_line":12}', index=4)]),
                FakeResponse(output_text='The fix removes shell execution and remains syntactically safe.'),
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
                ]),
                FixResult(
                    scope='SNIPPET',
                    start_line=8,
                    end_line=9,
                    fixed_code='safe_cmd = [user_cmd]\nreturn subprocess.run(safe_cmd, shell=False, capture_output=True, text=True)',
                    explanation='Execute the command without invoking a shell.',
                ),
                VerificationResult(
                    is_true_positive=True,
                    reasoning='The proposed fix removes shell interpretation and preserves the handler flow.',
                ),
            ],
        )

        with mock.patch('SAST.agent.OpenAI', return_value=fake_client):
            result = run_sast_scan(scan_job.id)

        scan_job.refresh_from_db()
        self.assertEqual(scan_job.status, 'COMPLETED')
        self.assertIn('completed', result.lower())
        for call in fake_client.responses.create_calls:
            for item in call['input']:
                if isinstance(item, dict):
                    self.assertNotIn('status', item)
                    self.assertNotIn('index', item)
                    if item.get('type') in {'function_call', 'function_call_output'}:
                        self.assertNotIn('id', item)

    def test_run_sast_scan_persists_snippet_fix_fields_and_metadata(self):
        self.load_fixture_repo()
        scan_job = SASTScanJob.objects.create(project=self.project, status='PENDING')
        fake_client = FakeOpenAIClient(
            create_responses=[
                FakeResponse(output=[FakeFunctionCall('scan-1', 'list_directory', '{"directory":""}')]),
                FakeResponse(output=[FakeFunctionCall('scan-2', 'search_codebase', '{"query":"subprocess.run","directory":"app"}')]),
                FakeResponse(output=[FakeFunctionCall('scan-3', 'read_file', '{"filepath":"app/views.py","start_line":1,"end_line":20}')]),
                FakeResponse(output_text='The app uses user input in a shell command.'),
                FakeResponse(output=[FakeFunctionCall('fix-1', 'read_file', '{"filepath":"app/views.py","start_line":6,"end_line":12}')]),
                FakeResponse(output_text='A snippet-scoped fix is sufficient.'),
                FakeResponse(output=[FakeFunctionCall('verify-1', 'read_file', '{"filepath":"app/views.py","start_line":6,"end_line":12}')]),
                FakeResponse(output_text='The fix removes shell execution and remains syntactically safe.'),
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
                ]),
                FixResult(
                    scope='SNIPPET',
                    start_line=8,
                    end_line=9,
                    fixed_code='safe_cmd = [user_cmd]\nreturn subprocess.run(safe_cmd, shell=False, capture_output=True, text=True)',
                    explanation='Execute the command without invoking a shell.',
                ),
                VerificationResult(
                    is_true_positive=True,
                    reasoning='The proposed fix removes shell interpretation and preserves the handler flow.',
                ),
            ],
        )

        with mock.patch('SAST.agent.OpenAI', return_value=fake_client):
            result = run_sast_scan(scan_job.id)

        scan_job.refresh_from_db()
        self.assertEqual(scan_job.status, 'COMPLETED')
        self.assertIn('completed', result.lower())
        self.assertEqual(scan_job.agent_run_metadata['tool_call_count'], 3)
        self.assertEqual(scan_job.findings.count(), 1)

        fix = SASTFix.objects.get()
        self.assertEqual(fix.scope, 'SNIPPET')
        self.assertEqual(fix.start_line, 8)
        self.assertEqual(fix.end_line, 9)
