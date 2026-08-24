from django.urls import path

from . import views

app_name = "permissions"

urlpatterns = [
    path("roles/", views.RoleListCreateView.as_view(), name="role-list"),
    path("roles/<uuid:pk>/", views.RoleDetailView.as_view(), name="role-detail"),
    path("permissions/", views.PermissionListCreateView.as_view(), name="permission-list"),
    path("permissions/<uuid:pk>/", views.PermissionDetailView.as_view(), name="permission-detail"),
    path("field-permissions/", views.FieldPermissionListCreateView.as_view(), name="fieldperm-list"),
    path("field-permissions/<uuid:pk>/", views.FieldPermissionDetailView.as_view(), name="fieldperm-detail"),
    path("masking-rules/", views.MaskingRuleListCreateView.as_view(), name="masking-list"),
    path("masking-rules/<uuid:pk>/", views.MaskingRuleDetailView.as_view(), name="masking-detail"),
]
