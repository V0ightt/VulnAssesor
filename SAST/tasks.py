from celery import shared_task
from django.utils import timezone
from .models import Project, SASTScanJob
from .services import ProjectManager
from .agents.base import ScanCancelledError
from .agents.orchestrator import SASTScanOrchestrator
from .sast_tools import report_vulnerability, apply_fix
from .progress import record_project_event, record_scan_event
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def ingest_project_task(self, project_id):
    try:
        project = Project.objects.get(id=project_id)
        if project.status == 'CANCELLED':
            return f"Project {project.name} ingestion was cancelled before start."

        if project.ingestion_task_id != self.request.id:
            project.ingestion_task_id = self.request.id
        project.status = 'CLONING'
        project.save(update_fields=['ingestion_task_id', 'status'])
        record_project_event(
            project,
            phase='ingestion',
            event_type='started',
            title='Project ingestion started',
            detail='Workspace setup is running in the background.',
            payload={'task_id': self.request.id},
        )

        manager = ProjectManager(project)
        record_project_event(
            project,
            phase='workspace',
            event_type='workspace_prepared',
            title='Workspace prepared',
            detail='Project workspace directory is ready for source import.',
            payload={'workspace': str(manager.workspace_root)},
        )

        def progress_callback(event_type, detail, payload=None):
            record_project_event(
                project,
                phase='ingestion',
                event_type=event_type,
                title=detail,
                detail=detail,
                payload=payload or {},
            )

        if project.repository_url:
            manager.clone_repository(progress_callback=progress_callback)
        elif project.source_zip:
            manager.extract_zip(progress_callback=progress_callback)

        project.refresh_from_db(fields=['status'])
        if project.status == 'CANCELLED':
            record_project_event(
                project,
                phase='ingestion',
                event_type='cancelled',
                title='Project ingestion cancelled',
                detail='The project was cancelled before it became ready.',
            )
            return f"Project {project.name} ingestion cancelled by user."
        
        project.root_directory = str(manager.workspace_root)
        project.status = 'READY'
        project.save(update_fields=['root_directory', 'status'])
        record_project_event(
            project,
            phase='ingestion',
            event_type='ready',
            title='Project ready',
            detail='Source import finished and SAST scans can now run.',
            payload={'root_directory': project.root_directory},
        )
        return f"Project {project.name} ingested successfully."
    except Project.DoesNotExist:
        return f"Project {project_id} not found."
    except Exception as e:
        logger.error(f"Error ingesting project {project_id}: {str(e)}")
        if 'project' in locals():
            project.refresh_from_db(fields=['status'])
            if project.status != 'CANCELLED':
                project.status = 'FAILED'
                project.save(update_fields=['status'])
                record_project_event(
                    project,
                    phase='ingestion',
                    event_type='failed',
                    title='Project ingestion failed',
                    detail=str(e),
                )
        return f"Error ingesting project: {str(e)}"

@shared_task
def run_sast_scan(scan_job_id):
    try:
        scan_job = SASTScanJob.objects.get(id=scan_job_id)
        project = scan_job.project
        if project.status != 'READY':
            scan_job.status = 'FAILED'
            scan_job.agent_run_metadata = {
                'stop_reason': 'project_not_ready',
                'error': f"Project status is {project.status}. Scan can only start when the project is READY.",
            }
            scan_job.save(update_fields=['status', 'agent_run_metadata'])
            record_scan_event(
                scan_job,
                phase='scan',
                event_type='failed',
                title='SAST scan could not start',
                detail=scan_job.agent_run_metadata['error'],
            )
            return f"Scan failed: project {project.id} is not ready."

        scan_job.status = 'SCANNING'
        manager = ProjectManager(project)
        scan_job.commit_hash = manager.get_repository_head_commit()
        scan_job.save()
        record_scan_event(
            scan_job,
            phase='scan',
            event_type='started',
            title='SAST scan started',
            detail='The orchestrator is preparing repository exploration.',
            payload={'commit_hash': scan_job.commit_hash or ''},
        )

        try:
            orchestrator = SASTScanOrchestrator(project, scan_job=scan_job)
            provider_settings = orchestrator.provider_settings
            record_scan_event(
                scan_job,
                phase='provider',
                event_type='provider_ready',
                title='AI provider ready',
                detail=f"{provider_settings.get('provider_label', provider_settings.get('provider'))} configured for scan, fix, and verification phases.",
                payload={
                    'provider': provider_settings.get('provider'),
                    'scan_model': provider_settings.get('scan_model'),
                    'fix_model': provider_settings.get('fix_model'),
                    'verify_model': provider_settings.get('verify_model'),
                },
            )
        except ValueError as e:
            logger.error(f"SAST Agent initialization failed: {e}")
            scan_job.status = 'FAILED'
            scan_job.agent_run_metadata = {
                'stop_reason': 'provider_initialization_failed',
                'error': str(e),
            }
            scan_job.completed_at = timezone.now()
            scan_job.save(update_fields=['status', 'agent_run_metadata', 'completed_at'])
            record_scan_event(
                scan_job,
                phase='provider',
                event_type='failed',
                title='AI provider initialization failed',
                detail=str(e),
            )
            return f"Scan failed: {e}"

        scan_result = orchestrator.run()
        scan_job.agent_run_metadata = scan_result.metadata
        scan_job.save(update_fields=['agent_run_metadata'])
        record_scan_event(
            scan_job,
            phase='persist',
            event_type='findings_ready',
            title='Agent analysis complete',
            detail=f'{len(scan_result.findings)} confirmed finding result(s) are ready to persist.',
            payload={'finding_results': len(scan_result.findings)},
        )

        for specialist_result in scan_result.findings:
            scan_job.refresh_from_db(fields=['status'])
            if scan_job.status == 'CANCELLED':
                logger.info(f"Scan {scan_job_id} cancelled by user.")
                record_scan_event(
                    scan_job,
                    phase='cancel',
                    event_type='cancelled',
                    title='SAST scan cancelled',
                    detail='Persistence stopped because cancellation was requested.',
                )
                return f"Scan {scan_job_id} cancelled."

            finding_data = specialist_result.vulnerability.model_dump()
            record_scan_event(
                scan_job,
                phase='persist',
                event_type='finding',
                title=f"Persisting finding: {finding_data['title']}",
                detail=f"{finding_data['severity']} in {finding_data['file_path']}:{finding_data['line_number']}.",
                payload={
                    'severity': finding_data['severity'],
                    'file_path': finding_data['file_path'],
                    'line_number': finding_data['line_number'],
                    'vulnerability_type': specialist_result.vulnerability_type,
                },
            )
            finding = report_vulnerability(
                scan_job=scan_job,
                file_path=finding_data['file_path'],
                line_number=finding_data['line_number'],
                severity=finding_data['severity'],
                title=finding_data['title'],
                description=finding_data['description'],
                code_snippet=finding_data['code_snippet'],
            )
            finding.ai_explanation = finding_data.get('ai_explanation', '')
            finding.save()

            fix_data = specialist_result.fix
            if not fix_data:
                continue

            explanation = fix_data.explanation
            verification = specialist_result.verification
            if verification and not verification.is_true_positive:
                logger.warning(f"Fix verification failed for {finding.title}: {verification.reasoning}")
                explanation = f"Verification Failed: {verification.reasoning}\n\nOriginal Explanation: {explanation}"

            apply_fix(
                finding_id=finding.id,
                proposed_code=fix_data.fixed_code,
                explanation=explanation,
                scope=fix_data.scope,
                start_line=fix_data.start_line,
                end_line=fix_data.end_line,
            )
            record_scan_event(
                scan_job,
                phase='persist',
                event_type='fix',
                title='Proposed fix saved',
                detail=f"Stored a {fix_data.scope.lower()} fix for {finding.title}.",
                payload={
                    'finding_id': finding.id,
                    'scope': fix_data.scope,
                    'start_line': fix_data.start_line,
                    'end_line': fix_data.end_line,
                },
            )

        scan_job.status = 'COMPLETED'
        scan_job.completed_at = timezone.now()
        scan_job.save()
        record_scan_event(
            scan_job,
            phase='complete',
            event_type='completed',
            title='SAST scan completed',
            detail=f'Scan completed with {scan_job.findings.count()} persisted finding(s).',
            payload={'findings_count': scan_job.findings.count()},
        )
        
        project.last_scan = timezone.now()
        project.save()
        
        return f"Scan {scan_job_id} completed."
        
    except ScanCancelledError:
        if 'scan_job' in locals():
            scan_job.agent_run_metadata = {
                **getattr(locals().get('orchestrator'), 'last_scan_metadata', {}),
                'stop_reason': 'cancelled',
            }
            scan_job.save(update_fields=['agent_run_metadata'])
            record_scan_event(
                scan_job,
                phase='cancel',
                event_type='cancelled',
                title='SAST scan cancelled',
                detail='The active agent stopped after cancellation was requested.',
            )
        return f"Scan {scan_job_id} cancelled."
    except SASTScanJob.DoesNotExist:
        return f"ScanJob {scan_job_id} not found."
    except Exception as e:
        logger.error(f"Error running scan {scan_job_id}: {str(e)}")
        if 'scan_job' in locals():
            scan_job.status = 'FAILED'
            scan_job.completed_at = timezone.now()
            if 'orchestrator' in locals():
                orchestrator.last_scan_metadata = {
                    **getattr(orchestrator, 'last_scan_metadata', {}),
                    'stop_reason': 'failed',
                    'error': str(e),
                }
                scan_job.agent_run_metadata = orchestrator.last_scan_metadata
            scan_job.save()
            record_scan_event(
                scan_job,
                phase='failed',
                event_type='failed',
                title='SAST scan failed',
                detail=str(e),
            )
        return f"Error running scan: {str(e)}"
