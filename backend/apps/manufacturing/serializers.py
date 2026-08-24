from rest_framework import serializers

from .models import (
    BillOfMaterials,
    BomComponent,
    MaterialReservation,
    NonConformance,
    ProductionOperation,
    ProductionOrder,
    QualityCheck,
    Routing,
    RoutingStep,
    StockLot,
    WorkCenter,
)


def _ser(model_cls, read_only=None):
    ro = ["id", "workspace_id", "created_at", "updated_at"] + list(read_only or [])

    class _S(serializers.ModelSerializer):
        class Meta:
            model = model_cls
            exclude = ["deleted_at", "deleted_by", "created_by", "updated_by"]
            read_only_fields = ro
    return _S


WorkCenterSerializer = _ser(WorkCenter)
BomSerializer = _ser(BillOfMaterials, read_only=["number", "status"])
BomComponentSerializer = _ser(BomComponent)
RoutingSerializer = _ser(Routing)
RoutingStepSerializer = _ser(RoutingStep)
ProductionOrderSerializer = _ser(ProductionOrder, read_only=[
    "number", "status", "material_cost", "labor_cost", "overhead_cost", "total_cost",
    "good_qty", "scrap_qty", "journal_entry_id", "actual_start", "actual_finish"])
OperationSerializer = _ser(ProductionOperation)
ReservationSerializer = _ser(MaterialReservation)
QualityCheckSerializer = _ser(QualityCheck)
NcrSerializer = _ser(NonConformance)
StockLotSerializer = _ser(StockLot)
