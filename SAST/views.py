from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.http import HttpResponse, JsonResponse
from .models import Project, SASTScanJob, SASTFinding
from .services import ProjectManager
from .tasks import ingest_project_task, run_sast_scan
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
        
        # Trigger initial setup (clone/extract) asynchronously
        ingest_project_task.delay(project.id)
        
        return redirect('project_detail', project_id=project.id)
    
    return render(request, 'sast/project_create.html')

@login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    latest_scan = project.scans.order_by('-created_at').first()
    scan_history = project.scans.order_by('-created_at')[:10] # Get last 10 scans
    
    return render(request, 'sast/project_detail.html', {
        'project': project, 
        'latest_scan': latest_scan,
        'scan_history': scan_history
    })

@login_required
@never_cache
def scan_status(request, scan_id):
    scan = get_object_or_404(SASTScanJob, id=scan_id, project__owner=request.user)
    return render(request, 'sast/partials/scan_status.html', {'scan': scan})

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
        
        # Cancel any existing running scans for this project
        active_scans = SASTScanJob.objects.filter(
            project=project, 
            status__in=['PENDING', 'SCANNING', 'CLONING']
        )
        for scan in active_scans:
            scan.status = 'CANCELLED'
            scan.save()
        
        # Create Scan Job
        scan_job = SASTScanJob.objects.create(project=project, status='PENDING')
        
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
    return redirect('project_detail', project_id=scan.project.id)

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
