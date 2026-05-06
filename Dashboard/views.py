from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Count, Q, Sum
from .tasks import simple_test_task, run_specialist_scan
from .models import Website, NucleiTemplate, ScanJob, NucleiConfig, ScanResult, AIConfig, ScanProgressEvent
from .progress import record_scan_event
import subprocess
import json
from VulnAssesor.celery import app as celery_app

# Authentication Views

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')

# Main Dashboard (Command Center)

@login_required
def dashboard_view(request):
    """Comprehensive dashboard aggregating SAST + DAST data."""
    from SAST.models import Project, SASTScanJob, SASTFinding, SASTFix

    user = request.user

    # --- SAST Data ---
    projects = Project.objects.filter(owner=user)
    total_projects = projects.count()
    projects_ready = projects.filter(status='READY').count()
    projects_pending = projects.filter(status__in=['PENDING', 'CLONING']).count()

    sast_scans = SASTScanJob.objects.filter(project__owner=user)
    total_sast_scans = sast_scans.count()
    active_sast_scans = sast_scans.filter(status__in=['PENDING', 'SCANNING', 'CLONING'])
    active_sast_count = active_sast_scans.count()
    completed_sast_scans = sast_scans.filter(status='COMPLETED').count()

    sast_findings = SASTFinding.objects.filter(scan_job__project__owner=user)
    total_sast_findings = sast_findings.count()
    sast_critical = sast_findings.filter(severity='CRITICAL').count()
    sast_high = sast_findings.filter(severity='HIGH').count()
    sast_medium = sast_findings.filter(severity='MEDIUM').count()
    sast_low = sast_findings.filter(severity='LOW').count()
    sast_info = sast_findings.filter(severity='INFO').count()

    sast_fixes = SASTFix.objects.filter(finding__scan_job__project__owner=user)
    total_fixes = sast_fixes.count()
    fixes_pending = sast_fixes.filter(status='PENDING').count()
    fixes_accepted = sast_fixes.filter(status='ACCEPTED').count()
    fixes_rejected = sast_fixes.filter(status='REJECTED').count()

    # --- DAST Data ---
    websites = Website.objects.filter(owner=user)
    total_websites = websites.count()

    dast_scans = ScanJob.objects.filter(website__owner=user)
    total_dast_scans = dast_scans.count()
    active_dast_scans = dast_scans.filter(status__in=['PENDING', 'RUNNING'])
    active_dast_count = active_dast_scans.count()
    completed_dast_scans = dast_scans.filter(status='COMPLETED').count()

    dast_results = ScanResult.objects.filter(job__website__owner=user)
    total_dast_findings = dast_results.count()
    dast_critical = dast_results.filter(severity='critical').count()
    dast_high = dast_results.filter(severity='high').count()
    dast_medium = dast_results.filter(severity='medium').count()
    dast_low = dast_results.filter(severity='low').count()
    dast_info = dast_results.filter(severity='info').count()

    # --- Agent Metadata (tool calls, etc.) ---
    total_tool_calls = 0
    total_compactions = 0
    tool_counts_agg = {}
    for scan in sast_scans.filter(agent_run_metadata__isnull=False):
        meta = scan.agent_run_metadata or {}
        total_tool_calls += meta.get('tool_call_count', 0)
        total_compactions += meta.get('compactions', 0)
        for tool_name, cnt in meta.get('tool_counts', {}).items():
            tool_counts_agg[tool_name] = tool_counts_agg.get(tool_name, 0) + cnt

    # --- Recent Activity ---
    recent_sast = list(sast_scans.select_related('project').order_by('-created_at')[:5])
    recent_dast = list(dast_scans.select_related('website').order_by('-created_at')[:5])

    # --- Active Scans (for live indicators) ---
    active_scans_list = []
    for s in active_sast_scans.select_related('project')[:5]:
        active_scans_list.append({
            'type': 'SAST',
            'name': s.project.name,
            'status': s.status,
            'id': s.id,
            'started': s.created_at.isoformat(),
        })
    for s in active_dast_scans.select_related('website')[:5]:
        active_scans_list.append({
            'type': 'DAST',
            'name': s.website.name,
            'status': s.status,
            'id': s.id,
            'started': s.created_at.isoformat(),
        })

    # --- Per-project summary for table ---
    project_summaries = []
    for p in projects.order_by('-updated_at')[:10]:
        p_findings = SASTFinding.objects.filter(scan_job__project=p)
        p_scans = p.scans.count()
        latest = p.scans.order_by('-created_at').first()
        project_summaries.append({
            'id': p.id,
            'name': p.name,
            'status': p.status,
            'total_scans': p_scans,
            'total_findings': p_findings.count(),
            'critical': p_findings.filter(severity='CRITICAL').count(),
            'high': p_findings.filter(severity='HIGH').count(),
            'last_scan': latest.created_at if latest else None,
            'last_scan_status': latest.status if latest else None,
        })

    context = {
        # Totals
        'total_projects': total_projects,
        'projects_ready': projects_ready,
        'projects_pending': projects_pending,
        'total_websites': total_websites,
        # SAST
        'total_sast_scans': total_sast_scans,
        'active_sast_count': active_sast_count,
        'completed_sast_scans': completed_sast_scans,
        'total_sast_findings': total_sast_findings,
        'sast_critical': sast_critical,
        'sast_high': sast_high,
        'sast_medium': sast_medium,
        'sast_low': sast_low,
        'sast_info': sast_info,
        # DAST
        'total_dast_scans': total_dast_scans,
        'active_dast_count': active_dast_count,
        'completed_dast_scans': completed_dast_scans,
        'total_dast_findings': total_dast_findings,
        'dast_critical': dast_critical,
        'dast_high': dast_high,
        'dast_medium': dast_medium,
        'dast_low': dast_low,
        'dast_info': dast_info,
        # Fixes
        'total_fixes': total_fixes,
        'fixes_pending': fixes_pending,
        'fixes_accepted': fixes_accepted,
        'fixes_rejected': fixes_rejected,
        # Agent
        'total_tool_calls': total_tool_calls,
        'total_compactions': total_compactions,
        'tool_counts_json': json.dumps(tool_counts_agg),
        # Active & Recent
        'active_scans_json': json.dumps(active_scans_list),
        'active_total': active_sast_count + active_dast_count,
        'recent_sast': recent_sast,
        'recent_dast': recent_dast,
        # Project table
        'project_summaries': project_summaries,
        # Severity chart data (combined)
        'severity_json': json.dumps({
            'critical': sast_critical + dast_critical,
            'high': sast_high + dast_high,
            'medium': sast_medium + dast_medium,
            'low': sast_low + dast_low,
            'info': sast_info + dast_info,
        }),
    }
    context.update(_dashboard_live_context(user))
    return render(request, 'dashboard/main_dashboard.html', context)


@login_required
def dashboard_live_operations_view(request):
    """Live command-center activity partial for HTMX polling."""
    context = _dashboard_live_context(request.user)
    context['include_oob'] = True
    return render(
        request,
        'dashboard/partials/live_operations.html',
        context,
    )


def _dashboard_live_context(user):
    from SAST.models import Project, SASTScanJob, SASTFinding, SASTFix, ProjectProgressEvent

    active_sast_scans = SASTScanJob.objects.filter(
        project__owner=user,
        status__in=['PENDING', 'SCANNING', 'CLONING'],
    ).select_related('project').order_by('-created_at')[:5]
    active_dast_scans = ScanJob.objects.filter(
        website__owner=user,
        status__in=['PENDING', 'RUNNING'],
    ).select_related('website').order_by('-created_at')[:5]
    ingesting_projects = Project.objects.filter(
        owner=user,
        status__in=['PENDING', 'CLONING'],
    ).order_by('-updated_at')[:5]

    operations = []
    for scan in active_sast_scans:
        operations.append({
            'kind': 'SAST',
            'name': scan.project.name,
            'status': scan.status,
            'url': reverse_url('project_detail', scan.project.id),
            'started': scan.created_at,
            'events': scan.progress_events.order_by('-sequence')[:4],
        })
    for scan in active_dast_scans:
        operations.append({
            'kind': 'DAST',
            'name': scan.website.name,
            'status': scan.status,
            'url': reverse_url('dast'),
            'started': scan.created_at,
            'events': scan.progress_events.order_by('-sequence')[:4],
        })
    for project in ingesting_projects:
        operations.append({
            'kind': 'INGEST',
            'name': project.name,
            'status': project.status,
            'url': reverse_url('project_detail', project.id),
            'started': project.updated_at,
            'events': project.progress_events.filter(scan_job__isnull=True).order_by('-sequence')[:4],
        })

    latest_sast_events = ProjectProgressEvent.objects.filter(
        project__owner=user,
    ).select_related('project', 'scan_job').order_by('-created_at')[:8]
    latest_dast_events = ScanProgressEvent.objects.filter(
        scan_job__website__owner=user,
    ).select_related('scan_job', 'scan_job__website').order_by('-created_at')[:8]

    latest_security_signals = []
    for finding in SASTFinding.objects.filter(
        scan_job__project__owner=user,
        severity__in=['CRITICAL', 'HIGH'],
    ).select_related('scan_job__project').order_by('-id')[:5]:
        latest_security_signals.append({
            'kind': 'SAST',
            'severity': finding.severity,
            'title': finding.title,
            'target': finding.file_path,
            'url': reverse_url('project_detail', finding.scan_job.project.id),
        })
    for finding in ScanResult.objects.filter(
        job__website__owner=user,
        severity__in=['critical', 'high'],
    ).select_related('job__website').order_by('-created_at')[:5]:
        latest_security_signals.append({
            'kind': 'DAST',
            'severity': finding.severity.upper(),
            'title': finding.vulnerability_name,
            'target': finding.target_url,
            'url': reverse_url('scan_results', finding.job.id),
        })
    latest_security_signals = latest_security_signals[:6]

    failed_sast_count = SASTScanJob.objects.filter(project__owner=user, status='FAILED').count()
    failed_dast_count = ScanJob.objects.filter(website__owner=user, status='FAILED').count()
    failed_ingestion_count = Project.objects.filter(owner=user, status='FAILED').count()
    pending_fix_count = SASTFix.objects.filter(
        finding__scan_job__project__owner=user,
        status='PENDING',
    ).count()
    ai_config = AIConfig.get_config()
    key_statuses = ai_config.key_statuses()
    provider_key_status = key_statuses.get(ai_config.provider, {})
    attention_items = []
    if failed_sast_count or failed_dast_count:
        attention_items.append(f'{failed_sast_count + failed_dast_count} failed scan(s)')
    if failed_ingestion_count:
        attention_items.append(f'{failed_ingestion_count} failed ingestion(s)')
    if pending_fix_count:
        attention_items.append(f'{pending_fix_count} pending AI fix(es)')
    if provider_key_status and not provider_key_status.get('configured'):
        attention_items.append(f"{provider_key_status.get('env_var')} is missing")

    active_total = len(active_sast_scans) + len(active_dast_scans) + len(ingesting_projects)
    return {
        'live_operations': operations,
        'live_active_total': active_total,
        'latest_sast_events': latest_sast_events,
        'latest_dast_events': latest_dast_events,
        'latest_security_signals': latest_security_signals,
        'attention_items': attention_items,
        'provider_key_status': provider_key_status,
    }


def reverse_url(name, *args):
    from django.urls import reverse

    return reverse(name, args=args)


# DAST Page (formerly "Dashboard")

@login_required
def dast_view(request):
    """DAST page - websites and DAST scans (previously dashboard_view)."""
    websites = Website.objects.filter(owner=request.user)

    # Optimize query with select_related and prefetch_related
    recent_scans = ScanJob.objects.filter(
        website__owner=request.user
    ).select_related(
        'website', 'cancelled_by'
    ).prefetch_related(
        'results'
    ).order_by('-created_at')[:10]

    return render(request, 'dashboard/dast.html', {
        'websites': websites,
        'recent_scans': recent_scans,
    })

@login_required
def website_add_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        url = request.POST.get('url')
        if name and url:
            Website.objects.create(name=name, url=url, owner=request.user)
            messages.success(request, 'Website added successfully!')
            return HttpResponse(status=200)
        else:
            messages.error(request, 'Please provide both name and URL.')
            return HttpResponse(status=400)
    return redirect('dashboard')

@login_required
def website_edit_view(request, pk):
    website = get_object_or_404(Website, pk=pk, owner=request.user)
    if request.method == 'POST':
        name = request.POST.get('name')
        url = request.POST.get('url')
        if name and url:
            website.name = name
            website.url = url
            website.save()
            messages.success(request, 'Website updated successfully!')
            return HttpResponse(status=200)
        else:
            messages.error(request, 'Please provide both name and URL.')
            return HttpResponse(status=400)
    return redirect('dashboard')

@login_required
def website_delete_view(request, pk):
    website = get_object_or_404(Website, pk=pk, owner=request.user)
    if request.method == 'POST' or request.method == 'DELETE':
        website.delete()
        messages.success(request, 'Website deleted successfully!')
        return HttpResponse(status=200)
    return HttpResponse(status=405)


@csrf_exempt
@login_required
def test_celery_view(request):
    """
    A view to trigger the simple test task.
    """
    if request.method == 'POST':
        # Call the task and make it run for 10 seconds
        simple_test_task.delay(10)

        # Immediately return an HTMX snippet
        return HttpResponse("""
            <div class="message info" role="alert">
                Task sent to worker! It will run for 10s. Check your worker logs.
            </div>
        """)
    return HttpResponse(status=405)


# Nuclei Template Management Views

@login_required
def template_list_view(request):
    """
    Display all of the user's Nuclei templates.
    """
    templates = NucleiTemplate.objects.filter(owner=request.user)
    return render(request, 'dashboard/template_list.html', {'templates': templates})


@login_required
def template_create_view(request):
    """
    Create a new Nuclei template.
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        template_content = request.POST.get('template_content')

        if name and template_content:
            NucleiTemplate.objects.create(
                name=name,
                description=description or '',
                template_content=template_content,
                owner=request.user
            )
            messages.success(request, f'Template "{name}" created successfully!')
            return redirect('template_list')
        else:
            messages.error(request, 'Please provide at least a name and template content.')

    return render(request, 'dashboard/template_form.html', {
        'form_title': 'Create Nuclei Template',
        'submit_text': 'Create Template',
    })


@login_required
def template_edit_view(request, pk):
    """
    Edit an existing Nuclei template.
    """
    template = get_object_or_404(NucleiTemplate, pk=pk, owner=request.user)

    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        template_content = request.POST.get('template_content')

        if name and template_content:
            template.name = name
            template.description = description or ''
            template.template_content = template_content
            template.save()
            messages.success(request, f'Template "{name}" updated successfully!')
            return redirect('template_list')
        else:
            messages.error(request, 'Please provide at least a name and template content.')

    return render(request, 'dashboard/template_form.html', {
        'template': template,
        'form_title': 'Edit Nuclei Template',
        'submit_text': 'Update Template',
    })


@login_required
def template_delete_view(request, pk):
    """
    Delete a Nuclei template.
    """
    template = get_object_or_404(NucleiTemplate, pk=pk, owner=request.user)

    if request.method == 'DELETE' or request.method == 'POST':
        template_name = template.name
        template.delete()

        # Check if this is an HTMX or AJAX request (case-insensitive header check)
        if request.headers.get('HX-Request') or request.headers.get('Hx-Request') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Return success response for AJAX/HTMX
            return HttpResponse(status=200)
        else:
            messages.success(request, f'Template "{template_name}" deleted successfully!')
            return redirect('template_list')

    return HttpResponse(status=405)


# Scan Management Views

@login_required
def scan_create_view(request, website_pk):
    """
    Create a new scan job for a website.
    """
    website = get_object_or_404(Website, pk=website_pk, owner=request.user)

    if request.method == 'POST':
        # Get selected template IDs from the form
        template_ids = request.POST.getlist('templates')

        # Validate that all templates belong to the user (only if templates are selected)
        if template_ids:
            templates = NucleiTemplate.objects.filter(
                id__in=template_ids,
                owner=request.user
            )

            if templates.count() != len(template_ids):
                messages.error(request, 'Invalid template selection.')
                return redirect('dashboard')
        else:
            # No templates selected - will use Nuclei default templates
            messages.info(request, 'No templates selected. Using Nuclei default templates.')

        # Create the scan job
        job = ScanJob.objects.create(
            website=website,
            status='PENDING'
        )
        record_scan_event(
            job,
            phase='queue',
            event_type='queued',
            title='DAST scan queued',
            detail=f'Scan queued for {website.url}.',
            payload={'target': website.url, 'template_count': len(template_ids)},
        )

        # Dispatch the task to Celery
        task = run_specialist_scan.delay(job.id, list(map(int, template_ids)) if template_ids else [])
        job.celery_task_id = task.id
        job.save(update_fields=['celery_task_id'])

        messages.success(request, f'Scan started for {website.name}!')

        if request.headers.get('HX-Request'):
            # Return HTMX snippet showing the pending scan
            return render(request, 'dashboard/scan_row.html', {'scan': job})

        return redirect('dashboard')

    # GET request - show template selection form
    templates = NucleiTemplate.objects.filter(owner=request.user)
    return render(request, 'dashboard/scan_create.html', {
        'website': website,
        'templates': templates,
    })


@login_required
def scan_status_view(request, scan_pk):
    """
    Return the current status of a scan job (for HTMX polling).
    Optimized to only fetch necessary data.
    """
    # Use select_related to avoid N+1 queries
    scan = get_object_or_404(
        ScanJob.objects.select_related('website', 'cancelled_by'),
        pk=scan_pk,
        website__owner=request.user
    )

    # Check if this is an HTMX request (case-insensitive header check)
    if request.headers.get('HX-Request') or request.headers.get('Hx-Request'):
        return render(request, 'dashboard/scan_row.html', {'scan': scan})

    return JsonResponse({
        'id': scan.id,
        'status': scan.status,
        'created_at': scan.created_at.isoformat(),
        'completed_at': scan.completed_at.isoformat() if scan.completed_at else None,
    })


@login_required
def scan_cancel_view(request, scan_pk):
    """
    Cancel a running or pending scan.
    """
    scan = get_object_or_404(ScanJob, pk=scan_pk, website__owner=request.user)

    if request.method == 'POST':
        # Only allow cancelling pending or running scans
        if scan.status in ['PENDING', 'RUNNING']:
            # Update scan status
            scan.status = 'CANCELLED'
            scan.cancelled_by = request.user
            scan.completed_at = timezone.now()
            scan.save()
            record_scan_event(
                scan,
                phase='cancel',
                event_type='cancelled',
                title='DAST scan cancellation requested',
                detail=f'{request.user.username} requested cancellation.',
                payload={'cancelled_by': request.user.username},
            )

            # Try to revoke the Celery task if it exists
            if scan.celery_task_id:
                try:
                    celery_app.control.revoke(scan.celery_task_id, terminate=True, signal='SIGKILL')
                    print(f"[Cancel] Revoked Celery task {scan.celery_task_id}")
                except Exception as e:
                    print(f"[Cancel] Failed to revoke task: {e}")

            # Refresh the scan object to get updated related objects
            scan.refresh_from_db()

            # Return HTMX response with updated row (check for HTMX request)
            if request.headers.get('HX-Request') or request.headers.get('Hx-Request'):
                return render(request, 'dashboard/scan_row.html', {'scan': scan})

            messages.success(request, f'Scan #{scan.id} has been cancelled.')
            return redirect('dashboard')
        else:
            messages.error(request, 'This scan cannot be cancelled.')

            # Return current scan row for HTMX
            if request.headers.get('HX-Request') or request.headers.get('Hx-Request'):
                return render(request, 'dashboard/scan_row.html', {'scan': scan})

            return redirect('dashboard')

    return HttpResponse(status=405)


@login_required
def scan_delete_view(request, scan_pk):
    """
    Delete a scan and its results.
    """
    scan = get_object_or_404(ScanJob, pk=scan_pk, website__owner=request.user)

    if request.method == 'POST':
        scan_id = scan.id
        scan.delete()  # This will cascade delete all related ScanResults

        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('HX-Request') or request.headers.get('Hx-Request'):
            return HttpResponse(status=200)
        else:
            messages.success(request, f'Scan #{scan_id} deleted successfully!')
            return redirect('dashboard')

    return HttpResponse(status=405)


@login_required
def scan_results_view(request, scan_pk):
    """
    Display detailed results of a completed scan.
    """
    scan = get_object_or_404(
        ScanJob.objects.select_related('website'),
        pk=scan_pk,
        website__owner=request.user
    )

    # Optimize results query - fetch only needed fields
    results = scan.results.all().order_by('-severity', '-created_at')

    # Group results by severity for better visualization
    results_by_severity = {
        'critical': results.filter(severity='critical'),
        'high': results.filter(severity='high'),
        'medium': results.filter(severity='medium'),
        'low': results.filter(severity='low'),
        'info': results.filter(severity='info'),
    }

    # Prepare results as JSON for Alpine.js
    import json
    from django.core.serializers.json import DjangoJSONEncoder
    
    # Define severity order for sorting
    severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}
    
    results_list = []
    for result in results:
        results_list.append({
            'id': result.id,
            'vulnerability_name': result.vulnerability_name,
            'template_name': result.template_name,
            'severity': result.severity,
            'severity_display': result.get_severity_display(),
            'target_url': result.target_url,
            'created_at': result.created_at.strftime('%b %d, %Y %H:%M:%S'),
            'raw_finding': result.raw_finding,
        })
    
    # Sort by severity (critical first) then by created_at
    results_list.sort(key=lambda x: (severity_order.get(x['severity'], 99), x['created_at']), reverse=True)
    
    return render(request, 'dashboard/scan_results.html', {
        'scan': scan,
        'results': results,
        'results_by_severity': results_by_severity,
        'results_list': results_list,
    })


# Nuclei Configuration View

@login_required
def nuclei_config_view(request):
    """
    View and edit scanner and AI provider configuration.
    """
    # if not request.user.is_staff:
    #     messages.error(request, 'You must be a staff member to access Nuclei configuration.')
    #     return redirect('dashboard')

    config = NucleiConfig.get_config()
    ai_config = AIConfig.get_config()
    active_tab = request.GET.get('tab', 'nuclei')

    if request.method == 'POST':
        try:
            def safe_int(value, default):
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return default

            if request.POST.get('config_section') == 'ai':
                provider = request.POST.get('provider', ai_config.provider)
                valid_providers = {choice[0] for choice in AIConfig.PROVIDER_CHOICES}
                if provider not in valid_providers:
                    raise ValueError('Invalid AI provider selected.')

                ai_config.provider = provider
                provider_fields = {
                    'openai': ('openai_scan_model', 'openai_fix_model'),
                    'anthropic': ('anthropic_scan_model', 'anthropic_fix_model'),
                    'deepseek': ('deepseek_scan_model', 'deepseek_fix_model'),
                }
                for provider_name, fields in provider_fields.items():
                    defaults = AIConfig.provider_defaults()[provider_name]
                    default_values = (
                        defaults['scan_model'],
                        defaults['fix_model'],
                    )
                    for field, default_value in zip(fields, default_values):
                        setattr(ai_config, field, request.POST.get(field, '').strip() or default_value)
                ai_config.openai_api_key_env_var = request.POST.get('openai_api_key_env_var', 'OPENAI_API_KEY').strip() or 'OPENAI_API_KEY'
                ai_config.anthropic_api_key_env_var = request.POST.get('anthropic_api_key_env_var', 'ANTHROPIC_API_KEY').strip() or 'ANTHROPIC_API_KEY'
                ai_config.deepseek_api_key_env_var = request.POST.get('deepseek_api_key_env_var', 'DEEPSEEK_API_KEY').strip() or 'DEEPSEEK_API_KEY'
                ai_config.openai_base_url = request.POST.get('openai_base_url', '').strip()
                ai_config.anthropic_base_url = request.POST.get('anthropic_base_url', '').strip()
                ai_config.deepseek_base_url = request.POST.get('deepseek_base_url', 'https://api.deepseek.com').strip() or 'https://api.deepseek.com'
                ai_config.max_output_tokens = safe_int(request.POST.get('max_output_tokens'), ai_config.max_output_tokens)
                ai_config.request_timeout = safe_int(request.POST.get('request_timeout'), ai_config.request_timeout)
                ai_config.updated_by = request.user
                ai_config.save()

                messages.success(request, 'AI provider configuration updated successfully!')
                return redirect('/nuclei/config/?tab=ai')

            config.timeout = safe_int(request.POST.get('timeout'), config.timeout)
            config.rate_limit = safe_int(request.POST.get('rate_limit'), config.rate_limit)
            config.concurrency = safe_int(request.POST.get('concurrency'), config.concurrency)
            config.retries = safe_int(request.POST.get('retries'), config.retries)
            config.max_host_errors = safe_int(request.POST.get('max_host_errors'), config.max_host_errors)

            config.silent_mode = request.POST.get('silent_mode') == 'on'
            config.no_color = request.POST.get('no_color') == 'on'
            config.jsonl_output = request.POST.get('jsonl_output') == 'on'
            config.follow_redirects = request.POST.get('follow_redirects') == 'on'

            config.custom_args = request.POST.get('custom_args', '').strip()
            config.updated_by = request.user

            config.save()

            messages.success(request, 'Nuclei configuration updated successfully!')
            return redirect('nuclei_config')

        except (ValueError, TypeError) as e:
            messages.error(request, f'Invalid configuration value: {e}')

    # Generate example command
    example_command = config.build_command('https://example.com', '/tmp/templates')

    return render(request, 'dashboard/nuclei_config.html', {
        'config': config,
        'ai_config': ai_config,
        'ai_key_statuses': ai_config.key_statuses(),
        'active_tab': active_tab,
        'example_command': ' '.join(example_command),
    })


@login_required
def nuclei_update_templates_view(request):
    """
    Update Nuclei default templates using nuclei -ut command.
    """
    if request.method == 'POST':
        try:
            print("[Nuclei Update] Starting nuclei template update...")

            # Run nuclei -ut command to update templates
            result = subprocess.run(
                ['nuclei', '-ut'],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            print(f"[Nuclei Update] Command completed with return code: {result.returncode}")

            if result.stdout:
                print(f"[Nuclei Update] Output: {result.stdout}")

            if result.stderr:
                print(f"[Nuclei Update] Stderr: {result.stderr}")

            if result.returncode == 0:
                messages.success(request, 'Nuclei templates updated successfully!')
            else:
                error_msg = result.stderr if result.stderr else result.stdout
                messages.warning(request, f'Nuclei template update completed with warnings. Check logs for details.')

        except subprocess.TimeoutExpired:
            messages.error(request, 'Template update timed out after 5 minutes.')
        except FileNotFoundError:
            messages.error(request, 'Nuclei command not found. Make sure Nuclei is installed.')
        except Exception as e:
            messages.error(request, f'Failed to update templates: {str(e)}')

        return redirect('nuclei_config')

    return HttpResponse(status=405)

