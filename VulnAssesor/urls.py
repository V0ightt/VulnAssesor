"""
URL configuration for VulnAssesor project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from Dashboard import views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Authentication URLs
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard and Website CRUD URLs
    path('', views.dashboard_view, name='dashboard'),
    path('website/add/', views.website_add_view, name='website_add'),
    path('website/<int:pk>/edit/', views.website_edit_view, name='website_edit'),
    path('website/<int:pk>/delete/', views.website_delete_view, name='website_delete'),

    # Template Management URLs
    path('templates/', views.template_list_view, name='template_list'),
    path('templates/create/', views.template_create_view, name='template_create'),
    path('templates/<int:pk>/edit/', views.template_edit_view, name='template_edit'),
    path('templates/<int:pk>/delete/', views.template_delete_view, name='template_delete'),

    # Scan Management URLs
    path('scan/create/<int:website_pk>/', views.scan_create_view, name='scan_create'),
    path('scan/<int:scan_pk>/status/', views.scan_status_view, name='scan_status'),
    path('scan/<int:scan_pk>/cancel/', views.scan_cancel_view, name='scan_cancel'),
    path('scan/<int:scan_pk>/delete/', views.scan_delete_view, name='scan_delete'),
    path('scan/<int:scan_pk>/results/', views.scan_results_view, name='scan_results'),

    # Nuclei Configuration URL
    path('nuclei/config/', views.nuclei_config_view, name='nuclei_config'),
    path('nuclei/update-templates/', views.nuclei_update_templates_view, name='nuclei_update_templates'),

    # Testing URLs
    path('test-celery/', views.test_celery_view, name='test_celery'),
]
