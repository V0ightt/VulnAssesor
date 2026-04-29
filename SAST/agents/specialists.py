import json

from django.conf import settings

from .base import BaseToolCallingAgent
from .memory import merge_memory_metadata
from .schemas import FixResult, ScanResult, SpecialistFindingResult, VerificationResult


class BaseSpecialistAgent(BaseToolCallingAgent):
    vulnerability_type = 'OTHER'
    specialist_title = 'Generic Security Specialist'
    investigation_instructions = (
        'Investigate the surface as an application security issue. Confirm only exploitable findings.'
    )

    def __init__(self, *args, **kwargs):
        self.phase_metadata = []
        super().__init__(
            *args,
            system_context_extra=(
                f'You are the {self.specialist_title}. '
                'Confirm or reject one orchestrator-provided vulnerability surface. '
                'Use repository tools before confirming exploitability. '
                'Return structured data only when evidence supports it.'
            ),
            **kwargs,
        )

    def run(self, surface):
        self.phase_metadata = []
        vulnerabilities = self.investigate(surface)
        results = []

        for vulnerability in vulnerabilities:
            self.ensure_scan_active()
            fix = self.generate_fix(vulnerability)
            self.ensure_scan_active()
            verification = self.verify_fix(vulnerability, fix)
            result = SpecialistFindingResult(
                surface_id=surface.surface_id,
                vulnerability_type=surface.vulnerability_type,
                vulnerability=vulnerability,
                fix=fix,
                verification=verification,
            )
            results.append(result)

        self.last_metadata = self._build_specialist_metadata()
        return [
            result.model_copy(update={'specialist_metadata': self.last_metadata})
            for result in results
        ]

    def investigate(self, surface):
        exploration = self._run_tool_loop(
            task_prompt=(
                f'{self.investigation_instructions}\n\n'
                'Trace attacker-controlled input to a security-sensitive sink. '
                'Return no findings if exploitability is not supported by code evidence. '
                'Do not produce fixes in this phase.\n\n'
                f'Orchestrator surface:\n{surface.model_dump_json()}'
            ),
            model=self.scan_model,
            max_tool_calls=settings.SAST_SCAN_SPECIALIST_MAX_TOOL_CALLS,
        )
        self.phase_metadata.append({
            'phase': 'investigate',
            **exploration.memory.build_metadata(exploration.stop_reason, exploration.final_response_text),
        })
        parsed = self._parse_structured_output(
            model=self.scan_model,
            schema=ScanResult,
            system_prompt=(
                self.system_context
                + '\n\nConvert the specialist investigation transcript into confirmed vulnerability findings. '
                'Only include issues directly supported by gathered code evidence. '
                'If the surface is not exploitable, return an empty findings list.'
            ),
            user_prompt=exploration.memory.build_investigation_summary(exploration.final_response_text),
        )
        return parsed.findings

    def generate_fix(self, vulnerability):
        finding = vulnerability.model_dump() if hasattr(vulnerability, 'model_dump') else vulnerability
        line_end = finding.get('end_line') or finding['line_number']
        exploration = self._run_tool_loop(
            task_prompt=(
                f"Generate the smallest safe fix for '{finding['title']}' in {finding['file_path']} "
                f"at lines {finding['line_number']}-{line_end}. "
                'Use repository tools to inspect the vulnerable region and nearby code. '
                'Prefer a snippet-scoped fix. Use FILE scope only if you have read and need to replace the entire file.\n\n'
                f'Finding details:\n{json.dumps(finding, ensure_ascii=True)}'
            ),
            model=self.fix_model,
            max_tool_calls=settings.SAST_SCAN_SPECIALIST_MAX_TOOL_CALLS,
        )
        self.phase_metadata.append({
            'phase': 'fix',
            **exploration.memory.build_metadata(exploration.stop_reason, exploration.final_response_text),
        })
        return self._parse_structured_output(
            model=self.fix_model,
            schema=FixResult,
            system_prompt=(
                self.system_context
                + '\n\nReturn a structured fix. `scope` must be SNIPPET or FILE. '
                'Use precise start_line and end_line values for the replacement range.'
            ),
            user_prompt=exploration.memory.build_investigation_summary(exploration.final_response_text),
        )

    def verify_fix(self, vulnerability, fix):
        finding = vulnerability.model_dump() if hasattr(vulnerability, 'model_dump') else vulnerability
        fix_data = fix.model_dump() if hasattr(fix, 'model_dump') else fix
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
        self.phase_metadata.append({
            'phase': 'verify',
            **exploration.memory.build_metadata(exploration.stop_reason, exploration.final_response_text),
        })
        return self._parse_structured_output(
            model=self.verify_model,
            schema=VerificationResult,
            system_prompt='You are a QA engineer verifying AI-generated security fixes. Return structured verification only.',
            user_prompt=exploration.memory.build_investigation_summary(exploration.final_response_text),
        )

    def _build_specialist_metadata(self, stop_reason='completed'):
        metadata = merge_memory_metadata(self.phase_metadata, stop_reason=stop_reason)
        metadata['phases'] = self.phase_metadata
        metadata['specialist'] = self.specialist_title
        metadata['vulnerability_type'] = self.vulnerability_type
        return metadata


class SQLiSpecialistAgent(BaseSpecialistAgent):
    vulnerability_type = 'SQL_INJECTION'
    specialist_title = 'SQL Injection Specialist'
    investigation_instructions = (
        'Focus on SQL construction, ORM escape hatches, raw queries, database filters, and user-controlled query fragments.'
    )


class XSSSpecialistAgent(BaseSpecialistAgent):
    vulnerability_type = 'XSS'
    specialist_title = 'Cross-Site Scripting Specialist'
    investigation_instructions = (
        'Focus on template rendering, HTML escaping, JavaScript sinks, markdown rendering, and stored or reflected user input.'
    )


class AuthBypassSpecialistAgent(BaseSpecialistAgent):
    vulnerability_type = 'AUTH_BYPASS'
    specialist_title = 'Authentication Bypass Specialist'
    investigation_instructions = (
        'Focus on authentication checks, session handling, decorators, middleware, token validation, and route protection.'
    )


class PathTraversalSpecialistAgent(BaseSpecialistAgent):
    vulnerability_type = 'PATH_TRAVERSAL'
    specialist_title = 'Path Traversal Specialist'
    investigation_instructions = (
        'Focus on file path joins, archive extraction, upload/download handlers, static file serving, and path normalization.'
    )


class CommandInjectionSpecialistAgent(BaseSpecialistAgent):
    vulnerability_type = 'COMMAND_INJECTION'
    specialist_title = 'Command Injection Specialist'
    investigation_instructions = (
        'Focus on subprocess, shell execution, command construction, process arguments, and user-controlled command input.'
    )


class GenericSecuritySpecialistAgent(BaseSpecialistAgent):
    vulnerability_type = 'OTHER'
    specialist_title = 'Generic Security Specialist'
    investigation_instructions = (
        'Focus on confirming the specific security claim in the surface with code evidence and reject unsupported issues.'
    )
