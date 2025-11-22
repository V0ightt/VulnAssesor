from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from .tasks import simple_test_task, run_specialist_scan
from .models import Website, NucleiTemplate, ScanJob, ScanResult, NucleiConfig
import subprocess
from celery.result import AsyncResult
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

# Dashboard and Website CRUD Views

@login_required
def dashboard_view(request):
    websites = Website.objects.filter(owner=request.user)

    # Optimize query with select_related and prefetch_related
    recent_scans = ScanJob.objects.filter(
        website__owner=request.user
    ).select_related(
        'website', 'cancelled_by'
    ).prefetch_related(
        'results'
    ).order_by('-created_at')[:10]

    return render(request, 'dashboard/dashboard.html', {
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

        # Dispatch the task to Celery
        run_specialist_scan.delay(job.id, list(map(int, template_ids)) if template_ids else [])

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
    View and edit Nuclei CLI configuration (admin/staff only).
    """
    # if not request.user.is_staff:
    #     messages.error(request, 'You must be a staff member to access Nuclei configuration.')
    #     return redirect('dashboard')

    config = NucleiConfig.get_config()

    if request.method == 'POST':
        # Update configuration
        try:
            # Helper function to safely convert to int
            def safe_int(value, default):
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return default

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

