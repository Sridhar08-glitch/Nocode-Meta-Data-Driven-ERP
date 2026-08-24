"""Settlement serializers."""
from rest_framework import serializers

from .models import Allocation, SettlementDocument


class SettlementDocumentSerializer(serializers.ModelSerializer):
    outstanding = serializers.SerializerMethodField()

    class Meta:
        model = SettlementDocument
        fields = ["id", "partner_ref", "direction", "doc_type", "document_ref", "document_date",
                  "due_date", "amount", "allocated_amount", "outstanding", "account_code",
                  "currency", "source_module", "external_ref", "status"]

    def get_outstanding(self, obj):
        return str(obj.outstanding)


class SettlementDocumentCreateSerializer(serializers.Serializer):
    partner_ref = serializers.CharField()
    direction = serializers.ChoiceField(choices=["debit", "credit"])
    amount = serializers.DecimalField(max_digits=20, decimal_places=2)
    doc_type = serializers.CharField(default="invoice")
    document_ref = serializers.CharField(required=False, allow_blank=True)
    document_date = serializers.DateField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    account_code = serializers.CharField(required=False, allow_blank=True)
    currency = serializers.CharField(required=False, allow_blank=True)
    source_module = serializers.CharField(required=False, allow_blank=True)
    external_ref = serializers.CharField(required=False, allow_blank=True)


class AllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Allocation
        fields = ["id", "credit_document", "debit_document", "amount", "external_ref"]
