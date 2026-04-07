from django.conf import settings

def global_context(request):
    ctx = {
        'PERSONDB_THEME': getattr(settings, 'PERSONDB_THEME', 'matrix'),
        'APP_NAME': 'Persofona',
    }
    if hasattr(request, 'workspace') and request.workspace:
        ctx['current_workspace'] = request.workspace
        ctx['current_membership'] = request.membership
    if hasattr(request, 'user_workspaces'):
        ctx['user_workspaces'] = request.user_workspaces
    return ctx
