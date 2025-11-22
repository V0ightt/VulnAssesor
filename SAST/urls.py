from django.urls import path
from . import views

urlpatterns = [
    path('projects/', views.project_list, name='project_list'),
    path('projects/new/', views.project_create, name='project_create'),
    path('projects/<int:project_id>/', views.project_detail, name='project_detail'),
    path('projects/<int:project_id>/explorer/', views.file_explorer, name='file_explorer'),
    path('projects/<int:project_id>/viewer/', views.file_viewer, name='file_viewer'),
    path('projects/<int:project_id>/scan/', views.start_scan, name='start_scan'),
    path('scans/<int:scan_id>/cancel/', views.cancel_scan, name='sast_cancel_scan'),
    path('scans/<int:scan_id>/status/', views.scan_status, name='sast_scan_status'),
    path('projects/<int:project_id>/delete/', views.project_delete, name='project_delete'),
]
