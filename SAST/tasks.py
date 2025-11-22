from celery import shared_task
from .models import Project
from .services import ProjectManager
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
