from rest_framework import serializers

from .models import Installment, InstallmentPlan


class InstallmentSerializer(serializers.ModelSerializer):
    outstanding = serializers.SerializerMethodField()

    class Meta:
        model = Installment
        fields = [
            "id", "plan_id", "seq", "due_date", "amount", "paid_amount", "status", "paid_at",
            "late_fee_amount", "late_fee_charged", "reminder_sent_at", "dunning_level",
            "outstanding",
        ]
        read_only_fields = fields

    def get_outstanding(self, obj):
        return str(obj.outstanding)


class InstallmentPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstallmentPlan
        fields = [
            "id", "number", "subject_ref", "source_document_ref", "notify_ref", "total_amount",
            "currency", "num_installments", "frequency", "interval_days", "start_date",
            "grace_days", "late_fee_type", "late_fee_value", "receivable_account",
            "late_fee_income_account", "status", "external_ref", "created_at", "updated_at",
        ]
        read_only_fields = fields


class PlanCreateSerializer(serializers.Serializer):
    total_amount = serializers.DecimalField(max_digits=16, decimal_places=2)
    num_installments = serializers.IntegerField(min_value=1)
    start_date = serializers.DateField()
    frequency = serializers.CharField(required=False, default="monthly")
    interval_days = serializers.IntegerField(required=False, default=0)
    subject_ref = serializers.CharField(required=False, allow_blank=True, default="")
    source_document_ref = serializers.CharField(required=False, allow_blank=True, default="")
    notify_ref = serializers.CharField(required=False, allow_blank=True, default="")
    grace_days = serializers.IntegerField(required=False, default=0)
    late_fee_type = serializers.CharField(required=False, default="none")
    late_fee_value = serializers.DecimalField(
        max_digits=16, decimal_places=2, required=False, default=0)
    currency = serializers.CharField(required=False, allow_blank=True, default="")
    external_ref = serializers.CharField(required=False, allow_blank=True, default="")


class PaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=16, decimal_places=2)
    installment_id = serializers.UUIDField(required=False, allow_null=True, default=None)
