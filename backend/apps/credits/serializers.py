from rest_framework import serializers

from .models import CreditNote


class CreditNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditNote
        fields = [
            "id", "kind", "number", "subject_ref", "applies_to_ref", "amount", "currency",
            "reason", "gl_debit_account", "gl_credit_account", "external_ref", "status",
            "journal_entry_id", "reversal_entry_id", "created_at", "updated_at",
        ]
        read_only_fields = fields


class CreditIssueSerializer(serializers.Serializer):
    kind = serializers.CharField()
    amount = serializers.DecimalField(max_digits=16, decimal_places=2)
    subject_ref = serializers.CharField(required=False, allow_blank=True, default="")
    applies_to_ref = serializers.CharField(required=False, allow_blank=True, default="")
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    external_ref = serializers.CharField(required=False, allow_blank=True, default="")
    debit_account = serializers.CharField(required=False, allow_null=True, default=None)
    credit_account = serializers.CharField(required=False, allow_null=True, default=None)
    currency = serializers.CharField(required=False, allow_blank=True, default="")
    date = serializers.DateField(required=False, allow_null=True, default=None)
