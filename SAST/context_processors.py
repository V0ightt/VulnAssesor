from .models import Project

def user_projects(request):
    if request.user.is_authenticated:
        return {'sidebar_projects': Project.objects.filter(owner=request.user)}
    return {'sidebar_projects': []}
