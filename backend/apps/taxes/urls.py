"""Tax Engine URLs at /api/v1/taxes/."""
from django.urls import path

from . import views

urlpatterns = [
    path("calculate/", views.CalculateView.as_view(), name="tax-calculate"),
    path("summary/", views.SummaryView.as_view(), name="tax-summary"),
    path("authorities/", views.AuthorityList.as_view(), name="tax-authorities"),
    path("codes/", views.CodeList.as_view(), name="tax-codes"),
    path("codes/<uuid:pk>/", views.CodeDetail.as_view(), name="tax-code-detail"),
    path("codes/<uuid:pk>/rates/", views.CodeRates.as_view(), name="tax-code-rates"),
    path("groups/", views.GroupList.as_view(), name="tax-groups"),
    path("exemptions/", views.ExemptionList.as_view(), name="tax-exemptions"),
]
