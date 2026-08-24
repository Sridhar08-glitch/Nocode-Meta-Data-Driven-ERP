from django.urls import path

from . import views

app_name = "solution_templates"

urlpatterns = [
    path("", views.TemplateListView.as_view(), name="list"),
    path("library/", views.LibraryView.as_view(), name="library"),
    # Create Solution Wizard (P2.4B)
    path("wizard/options/", views.WizardOptionsView.as_view(), name="wizard_options"),
    path("wizard/resolve/", views.WizardResolveView.as_view(), name="wizard_resolve"),
    path("wizard/preview/", views.WizardPreviewView.as_view(), name="wizard_preview"),
    path("wizard/create/", views.WizardCreateView.as_view(), name="wizard_create"),
    path("installed/", views.InstalledListView.as_view(), name="installed"),
    path("installed/<uuid:installed_id>/uninstall/",
         views.InstalledUninstallView.as_view(), name="uninstall"),
    path("<uuid:template_id>/", views.TemplateDetailView.as_view(), name="detail"),
    path("<uuid:template_id>/install/",
         views.TemplateInstallView.as_view(), name="install"),
    path("<uuid:template_id>/publish/",
         views.TemplatePublishView.as_view(), name="publish"),
]
