from rest_framework import serializers

from .models import (
    AssetValuationSnapshot,
    DepreciationEntry,
    DepreciationSchedule,
    DisposalRecord,
)


def _ser(model_cls):
    class _S(serializers.ModelSerializer):
        class Meta:
            model = model_cls
            exclude = ["deleted_at", "deleted_by", "created_by", "updated_by"]
            read_only_fields = ["id", "workspace_id", "created_at", "updated_at"]
    return _S


ScheduleSerializer = _ser(DepreciationSchedule)
EntrySerializer = _ser(DepreciationEntry)
DisposalSerializer = _ser(DisposalRecord)
SnapshotSerializer = _ser(AssetValuationSnapshot)
