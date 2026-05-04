from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.http import HttpResponse, JsonResponse
from celery.result import AsyncResult
from .models import Project, SASTScanJob, SASTFinding, ProjectProgressEvent
from .services import ProjectManager
from .tasks import ingest_project_task, run_sast_scan
from .progress import record_project_event, record_scan_event
from pygments import highlight
from pygments.lexers import get_lexer_for_filename, TextLexer
from pygments.formatters import HtmlFormatter
import os

@login_required
def project_list(request):
    projects = Project.objects.filter(owner=request.user)
    return render(request, 'sast/project_list.html', {'projects': projects})

@login_required
def project_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        repo_url = request.POST.get('repository_url')
        zip_file = request.FILES.get('source_zip')
        
        project = Project.objects.create(
            name=name,
            repository_url=repo_url,
            source_zip=zip_file,
            owner=request.user
        )
        record_project_event(
            project,
            phase='queue',
            event_type='queued',
            title='Project ingestion queued',
            detail='The project source import task has been queued.',
            payload={'source': 'git' if repo_url else 'zip'},
        )
        
        # Trigger initial setup (clone/extract) asynchronously
        ingestion_task = ingest_project_task.delay(project.id)
        project.ingestion_task_id = ingestion_task.id
        project.save(update_fields=['ingestion_task_id'])
        
        return redirect('project_detail', project_id=project.id)
    
    return render(request, 'sast/project_create.html')

@login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    latest_scan = project.scans.order_by('-created_at').first()
    scan_history = project.scans.order_by('-created_at')[:10] # Get last 10 scans
    ingestion_events = project.progress_events.filter(scan_job__isnull=True).order_by('-sequence')[:12]
    scan_events = latest_scan.progress_events.order_by('-sequence')[:16] if latest_scan else []

    context = {
        'project': project, 
        'latest_scan': latest_scan,
        'scan_history': scan_history,
        'ingestion_events': ingestion_events,
        'scan_events': scan_events,
    }

    if request.headers.get('HX-Request') == 'true':
        return render(request, 'sast/partials/project_detail_content.html', context)

    return render(request, 'sast/project_detail.html', context)

@login_required
@never_cache
def scan_status(request, scan_id):
    scan = get_object_or_404(SASTScanJob, id=scan_id, project__owner=request.user)
    events = scan.progress_events.order_by('-sequence')[:16]
    return render(request, 'sast/partials/scan_status.html', {'scan': scan, 'scan_events': events})


@login_required
@never_cache
def ingestion_status(request, project_id):
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    events = project.progress_events.filter(scan_job__isnull=True).order_by('-sequence')[:16]
    return render(request, 'sast/partials/ingestion_status.html', {'project': project, 'ingestion_events': events})

@login_required
def file_explorer(request, project_id):
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    path = request.GET.get('path', '')
    manager = ProjectManager(project)
    
    if project.status != 'READY':
        return HttpResponse('<div style="padding: 10px; color: #8b949e;">Project is being ingested...</div>')
            
    items = manager.get_directory_structure(path)
    return render(request, 'sast/partials/file_explorer.html', {'items': items, 'project': project, 'current_path': path})

@login_required
def file_viewer(request, project_id):
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    path = request.GET.get('path', '')
    manager = ProjectManager(project)
    
    try:
        content = manager.get_file_content(path)
        try:
            lexer = get_lexer_for_filename(path)
        except:
            lexer = TextLexer()
            
        formatter = HtmlFormatter(style='monokai', linenos=True, cssclass='source')
        highlighted_code = highlight(content, lexer, formatter)
        css = formatter.get_style_defs('.source')
        
    except Exception as e:
        highlighted_code = f"Error reading file: {str(e)}"
        css = ""
        
    return render(request, 'sast/partials/file_viewer.html', {
        'project': project, 
        'path': path, 
        'code': highlighted_code,
        'css': css
    })

@login_required
def start_scan(request, project_id):
    if request.method == 'POST':
        project = get_object_or_404(Project, id=project_id, owner=request.user)

        if project.status != 'READY':
            return redirect('project_detail', project_id=project.id)
        
        # Cancel any existing running scans for this project
        active_scans = SASTScanJob.objects.filter(
            project=project, 
            status__in=['PENDING', 'SCANNING', 'CLONING']
        )
        for scan in active_scans:
            scan.status = 'CANCELLED'
            scan.save()
            record_scan_event(
                scan,
                phase='cancel',
                event_type='cancelled',
                title='Superseded by new scan',
                detail='A new scan was started for this project.',
            )
        
        # Create Scan Job
        scan_job = SASTScanJob.objects.create(project=project, status='PENDING')
        record_scan_event(
            scan_job,
            phase='queue',
            event_type='queued',
            title='SAST scan queued',
            detail='The multi-agent SAST workflow has been queued.',
            payload={'project_id': project.id},
        )
        
        # Trigger Task
        run_sast_scan.delay(scan_job.id)
        
        return redirect('project_detail', project_id=project.id)
    return redirect('project_detail', project_id=project_id)

@login_required
def cancel_scan(request, scan_id):
    if request.method == 'POST':
        scan = get_object_or_404(SASTScanJob, id=scan_id, project__owner=request.user)
        if scan.status in ['PENDING', 'SCANNING', 'CLONING']:
            scan.status = 'CANCELLED'
            scan.save()
            record_scan_event(
                scan,
                phase='cancel',
                event_type='cancelled',
                title='SAST scan cancellation requested',
                detail=f'{request.user.username} requested cancellation.',
                payload={'cancelled_by': request.user.username},
            )
    return redirect('project_detail', project_id=scan.project.id)

@login_required
def cancel_ingestion(request, project_id):
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    if request.method == 'POST' and project.status in ['PENDING', 'CLONING']:
        if project.ingestion_task_id:
            AsyncResult(project.ingestion_task_id).revoke(terminate=True)
        project.status = 'CANCELLED'
        project.save(update_fields=['status'])
        record_project_event(
            project,
            phase='cancel',
            event_type='cancelled',
            title='Project ingestion cancellation requested',
            detail=f'{request.user.username} requested cancellation.',
            payload={'cancelled_by': request.user.username},
        )
    return redirect('project_detail', project_id=project.id)

@login_required
def project_delete(request, project_id):
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    if request.method == 'POST':
        # Delete workspace files
        manager = ProjectManager(project)
        manager.delete_workspace()
        
        # Delete project (cascades to scans and findings)
        project.delete()
        return redirect('project_list')
    return redirect('project_list')
