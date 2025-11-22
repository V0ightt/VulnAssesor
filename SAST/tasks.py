from celery import shared_task
from django.utils import timezone
from .models import Project, SASTScanJob, SASTFinding, SASTFix
from .services import ProjectManager
from .agent import SASTAgent
from .sast_tools import list_project_files, read_file, report_vulnerability, apply_fix
import logging

logger = logging.getLogger(__name__)

@shared_task
def ingest_project_task(project_id):
    try:
        project = Project.objects.get(id=project_id)
        project.status = 'CLONING'
        project.save()

        manager = ProjectManager(project)
        if project.repository_url:
            manager.clone_repository()
        elif project.source_zip:
            manager.extract_zip()
        
        project.status = 'READY'
        project.save()
        return f"Project {project.name} ingested successfully."
    except Project.DoesNotExist:
        return f"Project {project_id} not found."
    except Exception as e:
        logger.error(f"Error ingesting project {project_id}: {str(e)}")
        if 'project' in locals():
            project.status = 'FAILED'
            project.save()
        return f"Error ingesting project: {str(e)}"

@shared_task
def run_sast_scan(scan_job_id):
    try:
        scan_job = SASTScanJob.objects.get(id=scan_job_id)
        scan_job.status = 'SCANNING'
        scan_job.save()
        
        project = scan_job.project
        try:
            agent = SASTAgent(project)
        except ValueError as e:
            logger.error(f"SAST Agent initialization failed: {e}")
            scan_job.status = 'FAILED'
            scan_job.save()
            return f"Scan failed: {e}"
        
        # Get list of files to scan
        files = list_project_files(project)
        
        for file_path in files:
            # Check for cancellation
            scan_job.refresh_from_db()
            if scan_job.status == 'CANCELLED':
                logger.info(f"Scan {scan_job_id} cancelled by user.")
                return f"Scan {scan_job_id} cancelled."

            try:
                content = read_file(project, file_path)
                findings = agent.scan_code(file_path, content)
                
                logger.info(f"File: {file_path} - Findings: {len(findings)}")

                for finding_data in findings:
                    # Save finding
                    finding = report_vulnerability(
                        scan_job=scan_job,
                        file_path=file_path,
                        line_number=finding_data['line_number'],
                        severity=finding_data['severity'],
                        title=finding_data['title'],
                        description=finding_data['description'],
                        code_snippet=finding_data['code_snippet']
                    )
                    finding.ai_explanation = finding_data.get('ai_explanation', '')
                    finding.save()
                    
                    # Generate Fix
                    fix_data = agent.generate_fix(finding_data, content)
                    
                    # Verify Fix (Loop)
                    verification = agent.verify_fix(content, fix_data['fixed_code'], finding_data['title'])
                    
                    if verification['verified']:
                        apply_fix(
                            finding_id=finding.id,
                            proposed_code=fix_data['fixed_code'],
                            explanation=fix_data['explanation']
                        )
                    else:
                        # In a real scenario, we might retry here
                        logger.warning(f"Fix verification failed for {finding.title}: {verification['reason']}")
                        # Still save the fix but maybe mark it as unverified or rejected?
                        # For now, we'll save it but append a note to the explanation
                        apply_fix(
                            finding_id=finding.id,
                            proposed_code=fix_data['fixed_code'],
                            explanation=f"Verification Failed: {verification['reason']}\n\nOriginal Explanation: {fix_data['explanation']}"
                        )
                        
            except Exception as e:
                logger.error(f"Error scanning file {file_path}: {str(e)}")
                continue
                
        scan_job.status = 'COMPLETED'
        scan_job.completed_at = timezone.now()
        scan_job.save()
        
        project.last_scan = timezone.now()
        project.save()
        
        return f"Scan {scan_job_id} completed."
        
    except SASTScanJob.DoesNotExist:
        return f"ScanJob {scan_job_id} not found."
    except Exception as e:
        logger.error(f"Error running scan {scan_job_id}: {str(e)}")
        if 'scan_job' in locals():
            scan_job.status = 'FAILED'
            scan_job.save()
        return f"Error running scan: {str(e)}"
