from django.urls import path
from . import views

app_name = 'core'
urlpatterns = [
    # Auth
    path('accounts/register/', views.RegisterView.as_view(), name='register'),
    path('accounts/login/', views.LoginView.as_view(), name='login'),
    path('accounts/logout/', views.LogoutView.as_view(), name='logout'),
    # Workspace
    path('workspace/pick/', views.WorkspacePickView.as_view(), name='workspace_pick'),
    path('workspace/new/', views.WorkspaceCreateView.as_view(), name='workspace_create'),
    path('workspace/<int:pk>/switch/', views.WorkspaceSwitchView.as_view(), name='workspace_switch'),
    path('workspace/settings/', views.WorkspaceSettingsView.as_view(), name='workspace_settings'),
    path('workspace/invite/', views.InviteCreateView.as_view(), name='invite_create'),
    path('workspace/invite/<int:pk>/revoke/', views.InviteRevokeView.as_view(), name='invite_revoke'),
    path('workspace/member/<int:pk>/remove/', views.MemberRemoveView.as_view(), name='member_remove'),
    path('workspace/member/<int:pk>/role/', views.MemberRoleView.as_view(), name='member_role'),
    path('join/<str:code>/', views.JoinWorkspaceView.as_view(), name='join_workspace'),
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    # Persons
    path('persons/', views.PersonListView.as_view(), name='person_list'),
    path('persons/new/', views.PersonCreateView.as_view(), name='person_create'),
    path('persons/<int:pk>/', views.PersonDetailView.as_view(), name='person_detail'),
    path('persons/<int:pk>/edit/', views.PersonUpdateView.as_view(), name='person_update'),
    path('persons/<int:pk>/delete/', views.PersonDeleteView.as_view(), name='person_delete'),
    path('persons/<int:pk>/fav/', views.ToggleFavView.as_view(), name='toggle_fav'),
    # Relationships
    path('persons/<int:person_pk>/rel/new/', views.RelCreateView.as_view(), name='rel_create'),
    path('rel/<int:pk>/delete/', views.RelDeleteView.as_view(), name='rel_delete'),
    # Documents
    path('persons/<int:person_pk>/doc/new/', views.DocCreateView.as_view(), name='doc_create'),
    path('doc/<int:pk>/delete/', views.DocDeleteView.as_view(), name='doc_delete'),
    # Tags
    path('tags/', views.TagListView.as_view(), name='tag_list'),
    path('tags/new/', views.TagCreateView.as_view(), name='tag_create'),
    path('tags/<int:pk>/', views.TagDetailView.as_view(), name='tag_detail'),
    path('tags/<int:pk>/edit/', views.TagUpdateView.as_view(), name='tag_update'),
    path('tags/<int:pk>/delete/', views.TagDeleteView.as_view(), name='tag_delete'),
    # Groups
    path('groups/', views.GroupListView.as_view(), name='group_list'),
    path('groups/new/', views.GroupCreateView.as_view(), name='group_create'),
    path('groups/<int:pk>/', views.GroupDetailView.as_view(), name='group_detail'),
    path('groups/<int:pk>/edit/', views.GroupUpdateView.as_view(), name='group_update'),
    path('groups/<int:pk>/delete/', views.GroupDeleteView.as_view(), name='group_delete'),
    # Data
    path('export/', views.ExportView.as_view(), name='export'),
    path('import/', views.ImportView.as_view(), name='import_data'),
    path('backup/', views.BackupView.as_view(), name='backup'),
    path('restore/', views.RestoreView.as_view(), name='restore'),
    # Network Map
    path('map/', views.NetworkMapView.as_view(), name='network_map'),
    path('api/graph/', views.NetworkDataView.as_view(), name='graph_data'),
    path('api/graph/full/', views.FullGraphDataView.as_view(), name='graph_data_full'),
]
