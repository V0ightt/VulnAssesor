from django.conf import settings

from Dashboard.models import AIConfig

from ..llm import build_provider
from ..progress import record_scan_event
from .base import BaseToolCallingAgent
from .memory import aggregate_scan_metadata
from .registry import SpecialistRegistry
from .schemas import (
    OrchestratorSurfaceResult,
    ScanExecutionResult,
    VulnerabilitySurface,
)


class OrchestratorAgent(BaseToolCallingAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            system_context_extra=(
                'You are a security scan orchestrator, not a vulnerability confirmer. '
                'Use tools to discover likely entrypoints, user-controlled inputs, auth boundaries, '
                'storage boundaries, file operations, template rendering, subprocess calls, '
                'deserialization, outbound requests, and database access. '
                'Return potential vulnerability surfaces with evidence paths and recommended files. '
                'Do not produce fixes. Do not report unsupported vulnerabilities as findings.'
            ),
            **kwargs,
        )

    def discover_surfaces(self):
        exploration = self._run_tool_loop(
            task_prompt=(
                'Broadly map this repository for potential vulnerability surfaces. '
                'Start from the repository root, identify entrypoints and trust boundaries, then search for '
                'request handlers, auth flows, storage access, file uploads/downloads, subprocess usage, '
                'template rendering, deserialization, secrets, outbound requests, and database access. '
                'Classify potential surfaces only; do not claim confirmed vulnerabilities and do not generate fixes.'
            ),
            model=self.scan_model,
            max_tool_calls=settings.SAST_SCAN_ORCHESTRATOR_MAX_TOOL_CALLS,
            progress_phase='orchestrator',
            progress_title='Orchestrator mapping repository surfaces',
        )
        self.last_metadata = exploration.memory.build_metadata(exploration.stop_reason, exploration.final_response_text)
        self._record_progress(
            'orchestrator',
            'structured_parse',
            'Building vulnerability surface map',
            'Converting gathered repository evidence into dispatchable specialist work.',
            {'tool_call_count': self.last_metadata.get('tool_call_count', 0)},
        )
        parsed = self._parse_structured_output(
            model=self.scan_model,
            schema=OrchestratorSurfaceResult,
            system_prompt=(
                self.system_context
                + '\n\nConvert the broad repository exploration transcript into dispatchable vulnerability surfaces. '
                'Return only potential surfaces. Each surface must include a vulnerability_type, rationale, '
                'evidence_paths, recommended_files, and priority. Do not produce confirmed findings or fixes.'
            ),
            user_prompt=exploration.memory.build_investigation_summary(exploration.final_response_text),
        )
        self._record_progress(
            'orchestrator',
            'surfaces_discovered',
            f'Discovered {len(parsed.surfaces)} potential surface(s)',
            'Potential surfaces are ready for specialist review.',
            {'surface_count': len(parsed.surfaces)},
        )
        return parsed.surfaces


class SASTScanOrchestrator:
    def __init__(self, project, scan_job=None, ai_config=None, provider=None, registry=None):
        self.project = project
        self.scan_job = scan_job
        self.ai_config = ai_config or AIConfig.get_config()
        self.provider = provider or build_provider(self.ai_config)
        self.provider_settings = self.ai_config.selected_provider_settings()
        self.registry = registry or SpecialistRegistry()
        self.last_scan_metadata = {}

    def run(self):
        orchestrator_metadata = {}
        specialist_metadata_entries = []
        active_specialist = None
        active_surface = None
        findings = []

        orchestrator = OrchestratorAgent(
            self.project,
            scan_job=self.scan_job,
            provider=self.provider,
            ai_config=self.ai_config,
            provider_settings=self.provider_settings,
        )

        try:
            self._ensure_scan_active()
            self._record_progress(
                'orchestrator',
                'started',
                'Orchestrator started',
                'Broad repository exploration is underway.',
            )
            surfaces = orchestrator.discover_surfaces()
            orchestrator_metadata = orchestrator.last_metadata
            surfaces = self._limit_surfaces(self._dedupe_surfaces(surfaces))
            self._record_progress(
                'orchestrator',
                'dispatch_ready',
                f'{len(surfaces)} surface(s) selected for specialist review',
                'Deduplicated and prioritized surfaces will run sequentially.',
                {'surface_count': len(surfaces)},
            )

            for surface in surfaces:
                self._ensure_scan_active()
                self._record_progress(
                    'specialist',
                    'specialist_started',
                    f'{surface.vulnerability_type} specialist started',
                    surface.title,
                    {
                        'surface_id': surface.surface_id,
                        'vulnerability_type': surface.vulnerability_type,
                        'priority': surface.priority,
                        'evidence_paths': surface.evidence_paths,
                    },
                )
                specialist = self.registry.create(
                    surface.vulnerability_type,
                    self.project,
                    scan_job=self.scan_job,
                    provider=self.provider,
                    ai_config=self.ai_config,
                    provider_settings=self.provider_settings,
                )
                active_specialist = specialist
                active_surface = surface
                surface_results = specialist.run(surface)
                findings.extend(surface_results)
                self._record_progress(
                    'specialist',
                    'specialist_completed',
                    f'{surface.vulnerability_type} specialist completed',
                    f'{len(surface_results)} confirmed finding result(s) from this surface.',
                    {
                        'surface_id': surface.surface_id,
                        'vulnerability_type': surface.vulnerability_type,
                        'finding_results': len(surface_results),
                    },
                )
                specialist_metadata_entries.append({
                    'surface_id': surface.surface_id,
                    'vulnerability_type': surface.vulnerability_type,
                    'metadata': specialist.last_metadata,
                })
                active_specialist = None
                active_surface = None
                self._ensure_scan_active()

            metadata = aggregate_scan_metadata(
                orchestrator_metadata,
                specialist_metadata_entries,
                stop_reason='completed',
            )
            self.last_scan_metadata = metadata
            self._record_progress(
                'complete',
                'completed',
                'Agent workflow completed',
                f'The orchestrator and specialists produced {len(findings)} confirmed finding result(s).',
                {'finding_results': len(findings)},
            )
            return ScanExecutionResult(findings=findings, metadata=metadata)
        except Exception:
            if not orchestrator_metadata:
                orchestrator_metadata = getattr(orchestrator, 'last_metadata', {})
            if active_specialist and active_surface:
                specialist_metadata_entries.append({
                    'surface_id': active_surface.surface_id,
                    'vulnerability_type': active_surface.vulnerability_type,
                    'metadata': getattr(active_specialist, 'last_metadata', {}),
                })
            self.last_scan_metadata = aggregate_scan_metadata(
                orchestrator_metadata,
                specialist_metadata_entries,
                stop_reason='cancelled' if self._is_cancelled() else 'failed',
            )
            raise

    def _ensure_scan_active(self):
        if not self.scan_job:
            return
        self.scan_job.refresh_from_db(fields=['status'])
        if self.scan_job.status == 'CANCELLED':
            from .base import ScanCancelledError

            raise ScanCancelledError(f'Scan {self.scan_job.id} cancelled.')

    def _is_cancelled(self):
        if not self.scan_job:
            return False
        self.scan_job.refresh_from_db(fields=['status'])
        return self.scan_job.status == 'CANCELLED'

    def _limit_surfaces(self, surfaces):
        return surfaces[:settings.SAST_SCAN_MAX_SPECIALISTS]

    def _dedupe_surfaces(self, surfaces):
        seen = set()
        deduped = []
        for surface in surfaces:
            if not isinstance(surface, VulnerabilitySurface):
                surface = VulnerabilitySurface.model_validate(surface)
            key = (
                (surface.vulnerability_type or 'OTHER').upper(),
                tuple(sorted(self._normalize_path(path) for path in surface.evidence_paths)),
                ' '.join(surface.title.lower().split()),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(surface)
        return deduped

    def _normalize_path(self, path):
        return (path or '').replace('\\', '/').strip().strip('/')

    def _record_progress(self, phase, event_type, title, detail='', payload=None):
        if self.scan_job:
            record_scan_event(
                self.scan_job,
                phase=phase,
                event_type=event_type,
                title=title,
                detail=detail,
                payload=payload or {},
            )
