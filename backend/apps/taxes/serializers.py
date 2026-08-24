"""Tax Engine serializers."""
from rest_framework import serializers

from .models import TaxAuthority, TaxCode, TaxExemption, TaxGroup, TaxRate


class TaxAuthoritySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxAuthority
        fields = ["id", "code", "name", "country", "level", "registration_no", "is_active"]


class TaxRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxRate
        fields = ["id", "tax_code", "rate", "effective_from", "effective_to", "is_active"]
        read_only_fields = ["tax_code"]


class TaxCodeSerializer(serializers.ModelSerializer):
    rates = TaxRateSerializer(many=True, read_only=True)

    class Meta:
        model = TaxCode
        fields = ["id", "code", "name", "authority", "tax_type", "is_inclusive", "is_compound",
                  "is_recoverable", "is_withholding", "rounding", "output_account_code",
                  "input_account_code", "is_active", "rates"]


class TaxGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxGroup
        fields = ["id", "code", "name", "is_active"]


class TaxExemptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxExemption
        fields = ["id", "partner_ref", "tax_code", "tax_group", "certificate_no", "reason",
                  "effective_from", "effective_to", "is_active"]


class TaxCalculateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=20, decimal_places=2)
    tax_code = serializers.CharField(required=False, allow_blank=True)
    tax_group = serializers.CharField(required=False, allow_blank=True)
    on_date = serializers.DateField(required=False, allow_null=True)
    partner_ref = serializers.CharField(required=False, allow_blank=True)
    inclusive = serializers.BooleanField(required=False, allow_null=True, default=None)
    quantity = serializers.IntegerField(required=False, default=1)
