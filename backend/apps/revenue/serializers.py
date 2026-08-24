"""Revenue Recognition serializers."""
from rest_framework import serializers

from .models import RevenueSchedule, RevenueScheduleLine


class RevenueScheduleLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = RevenueScheduleLine
        fields = ["id", "period_no", "period_date", "amount", "recognized", "recognized_at"]


class RevenueScheduleSerializer(serializers.ModelSerializer):
    lines = RevenueScheduleLineSerializer(many=True, read_only=True)

    class Meta:
        model = RevenueSchedule
        fields = ["id", "number", "source_module", "source_ref", "external_ref", "partner_ref",
                  "method", "total_amount", "recognized_amount", "currency", "num_periods",
                  "start_date", "frequency", "deferred_account", "revenue_account", "status", "lines"]


class RevenueScheduleCreateSerializer(serializers.Serializer):
    total_amount = serializers.DecimalField(max_digits=20, decimal_places=2)
    method = serializers.ChoiceField(choices=["immediate", "straight_line", "milestone"],
                                     default="straight_line")
    num_periods = serializers.IntegerField(default=1)
    start_date = serializers.DateField(required=False, allow_null=True)
    frequency = serializers.CharField(default="monthly")
    source_module = serializers.CharField(required=False, allow_blank=True)
    source_ref = serializers.CharField(required=False, allow_blank=True)
    external_ref = serializers.CharField(required=False, allow_blank=True)
    partner_ref = serializers.CharField(required=False, allow_blank=True)
    currency = serializers.CharField(required=False, allow_blank=True)
    deferred_account = serializers.CharField(required=False, allow_blank=True)
    revenue_account = serializers.CharField(required=False, allow_blank=True)
    milestone_amounts = serializers.ListField(child=serializers.DecimalField(
        max_digits=20, decimal_places=2), required=False)
