"""DRF serializers for the General Ledger API (Phase P2.2)."""
from rest_framework import serializers

from .models import (
    AccountingPeriod,
    JournalEntry,
    JournalLine,
    LedgerAccount,
    PostingRule,
)


class LedgerAccountSerializer(serializers.ModelSerializer):
    normal_balance = serializers.CharField(read_only=True)

    class Meta:
        model = LedgerAccount
        fields = ["id", "code", "name", "account_type", "parent", "is_group", "is_active",
                  "currency", "description", "normal_balance", "created_by", "created_at", "updated_at"]
        read_only_fields = ["id", "normal_balance", "created_by", "created_at", "updated_at"]


class AccountingPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountingPeriod
        fields = ["id", "code", "name", "start_date", "end_date", "status", "fiscal_year",
                  "closed_at", "closed_by", "created_at", "updated_at"]
        read_only_fields = ["id", "status", "closed_at", "closed_by", "created_at", "updated_at"]


class JournalLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = JournalLine
        fields = ["id", "account", "account_code", "account_name", "line_no",
                  "debit", "credit", "memo", "partner_ref"]
        read_only_fields = ["id", "account_code", "account_name", "line_no"]


class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalLineSerializer(many=True, read_only=True)

    class Meta:
        model = JournalEntry
        fields = ["id", "entry_number", "date", "period", "memo", "currency", "status",
                  "source_module", "source_ref", "posting_rule_key", "posted_at", "posted_by",
                  "reverses", "lines", "created_by", "created_at", "updated_at"]
        read_only_fields = ["id", "entry_number", "status", "posted_at", "posted_by",
                            "reverses", "lines", "created_by", "created_at", "updated_at"]


class PostingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostingRule
        fields = ["id", "event_type", "name", "template", "is_active",
                  "created_by", "created_at", "updated_at"]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]
