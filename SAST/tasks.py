from celery import shared_task
from django.utils import timezone
from .models import Project, SASTScanJob
from .services import ProjectManager
from .agents.base import ScanCancelledError
from .agents.orchestrator import SASTScanOrchestrator
from .sast_tools import report_vulnerability, apply_fix
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

        manager = ProjectManager(project)
        if project.repository_url:
            manager.clone_repository()
        elif project.source_zip:
            manager.extract_zip()

        project.refresh_from_db(fields=['status'])
        if project.status == 'CANCELLED':
            return f"Project {project.name} ingestion cancelled by user."
        
        project.root_directory = str(manager.workspace_root)
        project.status = 'READY'
        project.save(update_fields=['root_directory', 'status'])
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
            return f"Scan failed: project {project.id} is not ready."

        scan_job.status = 'SCANNING'
        manager = ProjectManager(project)
        scan_job.commit_hash = manager.get_repository_head_commit()
        scan_job.save()

        try:
            orchestrator = SASTScanOrchestrator(project, scan_job=scan_job)
        except ValueError as e:
            logger.error(f"SAST Agent initialization failed: {e}")
            scan_job.status = 'FAILED'
            scan_job.agent_run_metadata = {
                'stop_reason': 'provider_initialization_failed',
                'error': str(e),
            }
            scan_job.completed_at = timezone.now()
            scan_job.save(update_fields=['status', 'agent_run_metadata', 'completed_at'])
            return f"Scan failed: {e}"

        scan_result = orchestrator.run()
        scan_job.agent_run_metadata = scan_result.metadata
        scan_job.save(update_fields=['agent_run_metadata'])

        for specialist_result in scan_result.findings:
            scan_job.refresh_from_db(fields=['status'])
            if scan_job.status == 'CANCELLED':
                logger.info(f"Scan {scan_job_id} cancelled by user.")
                return f"Scan {scan_job_id} cancelled."

            finding_data = specialist_result.vulnerability.model_dump()
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

        scan_job.status = 'COMPLETED'
        scan_job.completed_at = timezone.now()
        scan_job.save()
        
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
        return f"Scan {scan_job_id} cancelled."
    except SASTScanJob.DoesNotExist:
        return f"ScanJob {scan_job_id} not found."
    except Exception as e:
        logger.error(f"Error running scan {scan_job_id}: {str(e)}")
        if 'scan_job' in locals():
            scan_job.status = 'FAILED'
            if 'orchestrator' in locals():
                orchestrator.last_scan_metadata = {
                    **getattr(orchestrator, 'last_scan_metadata', {}),
                    'stop_reason': 'failed',
                    'error': str(e),
                }
                scan_job.agent_run_metadata = orchestrator.last_scan_metadata
            scan_job.save()
        return f"Error running scan: {str(e)}"
