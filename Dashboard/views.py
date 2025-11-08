from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.http import HttpResponse
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
