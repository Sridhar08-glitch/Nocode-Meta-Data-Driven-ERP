from django.urls import path

from . import views as v

app_name = "credits"

urlpatterns = [
    path("setup/", v.SetupView.as_view(), name="setup"),
    path("credits/", v.CreditList.as_view(), name="credit_list"),
    path("credits/<uuid:pk>/", v.CreditDetail.as_view(), name="credit_detail"),
    path("credits/<uuid:pk>/void/", v.CreditVoid.as_view(), name="credit_void"),
]
