from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    # Master data
    path("categories/", views.CategoryList.as_view(), name="category-list"),
    path("categories/<uuid:pk>/", views.CategoryDetail.as_view(), name="category-detail"),
    path("items/", views.ItemList.as_view(), name="item-list"),
    path("items/<uuid:pk>/", views.ItemDetail.as_view(), name="item-detail"),
    path("warehouses/", views.WarehouseList.as_view(), name="warehouse-list"),
    path("warehouses/<uuid:pk>/", views.WarehouseDetail.as_view(), name="warehouse-detail"),
    path("locations/", views.LocationList.as_view(), name="location-list"),
    path("locations/<uuid:pk>/", views.LocationDetail.as_view(), name="location-detail"),
    # Stock transactions
    path("receive/", views.ReceiveView.as_view(), name="receive"),
    path("issue/", views.IssueView.as_view(), name="issue"),
    path("adjust/", views.AdjustView.as_view(), name="adjust"),
    path("transfer/", views.TransferView.as_view(), name="transfer"),
    # Reports
    path("stock/", views.StockBalanceView.as_view(), name="stock-balance"),
    path("valuation/", views.ValuationView.as_view(), name="valuation"),
    path("movements/", views.MovementHistoryView.as_view(), name="movements"),
]
