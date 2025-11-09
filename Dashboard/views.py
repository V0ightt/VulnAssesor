from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.http import HttpResponse
from .tasks import simple_test_task
from .models import Website

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
    return render(request, 'dashboard/dashboard.html', {'websites': websites})

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