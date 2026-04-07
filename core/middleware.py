from django.shortcuts import redirect
from django.urls import reverse
from .models import Workspace, Membership

# URLs that don't need workspace or auth
PUBLIC_PATHS = ['/accounts/', '/join/', '/i18n/']


class WorkspaceMiddleware:
    """Sets request.workspace from session. Redirects to workspace picker if needed."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.workspace = None
        request.membership = None
        request.user_workspaces = []

        # Skip for unauthenticated or public paths
        if not request.user.is_authenticated or any(request.path.startswith(p) for p in PUBLIC_PATHS):
            return self.get_response(request)

        # Admin bypass
        if request.path.startswith('/admin/'):
            return self.get_response(request)

        # Load user workspaces
        memberships = Membership.objects.filter(user=request.user).select_related('workspace')
        request.user_workspaces = [m.workspace for m in memberships]

        # Get workspace from session
        ws_id = request.session.get('workspace_id')
        if ws_id:
            try:
                m = memberships.get(workspace_id=ws_id)
                request.workspace = m.workspace
                request.membership = m
            except Membership.DoesNotExist:
                del request.session['workspace_id']

        # If no workspace selected
        if not request.workspace:
            # Auto-select if user has exactly one
            if len(request.user_workspaces) == 1:
                request.workspace = request.user_workspaces[0]
                request.membership = memberships.first()
                request.session['workspace_id'] = request.workspace.id
            elif not request.path.startswith('/workspace'):
                # Redirect to workspace picker/creator
                return redirect('core:workspace_pick')

        return self.get_response(request)
