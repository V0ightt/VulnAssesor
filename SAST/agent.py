import json

from django.conf import settings

from Dashboard.models import AIConfig

from .agents.base import BaseToolCallingAgent, ScanCancelledError
from .agents.memory import ExplorationResult, MemoryEvent, ScanMemoryManager
from .agents.schemas import (
    FixResult,
    OrchestratorSurfaceResult,
    ScanExecutionResult,
    ScanResult,
    SpecialistFindingResult,
    VerificationResult,
    Vulnerability,
    VulnerabilitySurface,
)
from .llm import build_provider


class SASTAgent(BaseToolCallingAgent):
    """
    Deprecated compatibility facade for older imports.

    New SAST scans should use SAST.agents.orchestrator.SASTScanOrchestrator.
    This class preserves the old public methods while sharing the new base
    tool-calling implementation.
    """

    def __init__(self, project, scan_job=None):
        self.ai_config = AIConfig.get_config()
        self.provider = build_provider(self.ai_config)
        self.last_scan_metadata = {}
        super().__init__(
            project,
            scan_job=scan_job,
            provider=self.provider,
            ai_config=self.ai_config,
            provider_settings=self.ai_config.selected_provider_settings(),
        )

    def scan_project(self):
        exploration = self._run_tool_loop(
            task_prompt=(
                'Inspect this repository for exploitable vulnerabilities. '
                'Start from the repository root, map likely entrypoints and trust boundaries, then '
                'search for request handlers, auth flows, file uploads, subprocess usage, template rendering, '
                'deserialization, secrets, and dangerous sinks. Use tools only. '
                'When you have enough evidence, stop calling tools and summarize the vulnerabilities you found.'
            ),
            model=self.scan_model,
            max_tool_calls=settings.SAST_SCAN_MAX_TOOL_CALLS,
        )
        self.last_scan_metadata = exploration.memory.build_metadata(
            exploration.stop_reason,
            exploration.final_response_text,
        )
        parsed = self._parse_structured_output(
            model=self.scan_model,
            schema=ScanResult,
            system_prompt=(
                self.system_context
                + '\n\nConvert the investigation transcript into structured vulnerability findings. '
                'Only include issues directly supported by the gathered evidence. '
                'If no supported vulnerability exists, return an empty findings list.'
            ),
            user_prompt=exploration.memory.build_investigation_summary(exploration.final_response_text),
        )
        return [finding.model_dump() for finding in parsed.findings]

    def generate_fix(self, finding):
        line_end = finding.get('end_line') or finding['line_number']
        exploration = self._run_tool_loop(
            task_prompt=(
                f"Generate a secure fix for '{finding['title']}' in {finding['file_path']} "
                f"at lines {finding['line_number']}-{line_end}. "
                'Use repository tools to inspect the vulnerable region and nearby code. '
                'Prefer a snippet-scoped fix. Use FILE scope only if you have read and need to replace the entire file.\n\n'
                f'Finding details:\n{json.dumps(finding, ensure_ascii=True)}'
            ),
            model=self.fix_model,
            max_tool_calls=settings.SAST_SCAN_SPECIALIST_MAX_TOOL_CALLS,
        )
        result = self._parse_structured_output(
            model=self.fix_model,
            schema=FixResult,
            system_prompt=(
                self.system_context
                + '\n\nReturn a structured fix. `scope` must be SNIPPET or FILE. '
                'Use precise start_line and end_line values for the replacement range.'
            ),
            user_prompt=exploration.memory.build_investigation_summary(exploration.final_response_text),
        )
        return result.model_dump()

    def verify_fix(self, finding, fix_data):
        line_end = finding.get('end_line') or finding['line_number']
        exploration = self._run_tool_loop(
            task_prompt=(
                f"Verify whether the proposed fix for '{finding['title']}' in {finding['file_path']} "
                f"at lines {finding['line_number']}-{line_end} resolves the issue without introducing "
                'new security bugs or obvious syntax problems. Use repository tools to inspect only the '
                'necessary context.\n\n'
                f'Finding details:\n{json.dumps(finding, ensure_ascii=True)}\n\n'
                f'Proposed fix:\n{json.dumps(fix_data, ensure_ascii=True)}'
            ),
            model=self.verify_model,
            max_tool_calls=settings.SAST_SCAN_SPECIALIST_MAX_TOOL_CALLS,
        )
        result = self._parse_structured_output(
            model=self.verify_model,
            schema=VerificationResult,
            system_prompt='You are a QA engineer verifying AI-generated security fixes. Return structured verification only.',
            user_prompt=exploration.memory.build_investigation_summary(exploration.final_response_text),
        )
        return {
            'verified': result.is_true_positive,
            'reason': result.reasoning,
        }


__all__ = [
    'ExplorationResult',
    'FixResult',
    'MemoryEvent',
    'OrchestratorSurfaceResult',
    'SASTAgent',
    'ScanCancelledError',
    'ScanExecutionResult',
    'ScanMemoryManager',
    'ScanResult',
    'SpecialistFindingResult',
    'VerificationResult',
    'Vulnerability',
    'VulnerabilitySurface',
    'build_provider',
]
