from django.urls import path

from . import views

app_name = "procurement"

urlpatterns = [
    path("setup/", views.SetupView.as_view(), name="setup"),
    path("goods-receipts/<uuid:record_id>/post/",
         views.GoodsReceiptPostView.as_view(), name="post_receipt"),
    path("vendor-bills/<uuid:record_id>/post/",
         views.VendorBillPostView.as_view(), name="post_bill"),
    path("<slug:entity_slug>/", views.DocumentCreateView.as_view(), name="create_document"),
    path("<slug:entity_slug>/<uuid:record_id>/approve/",
         views.DocumentApproveView.as_view(), name="approve_document"),
]
