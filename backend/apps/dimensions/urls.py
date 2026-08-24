"""Financial Dimensions URLs at /api/v1/dimensions/."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.DimensionList.as_view(), name="dimension-list"),
    path("values/", views.ValueList.as_view(), name="dimension-values"),
    path("validate/", views.ValidateView.as_view(), name="dimension-validate"),
]
