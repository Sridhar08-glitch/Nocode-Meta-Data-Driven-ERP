"""DRF serializers for the approvals API."""
from rest_framework import serializers

from .models import ApprovalDecision, ApprovalProcess, ApprovalRequest


class ApprovalProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalProcess
        fields = ["id", "name", "slug", "entity_id", "trigger_condition_nql", "levels",
                  "on_approve_actions", "on_reject_actions", "is_active",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ApprovalDecisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalDecision
        fields = ["id", "level", "approver_id", "decision", "comment", "decided_at"]
        read_only_fields = fields


class ApprovalRequestSerializer(serializers.ModelSerializer):
    decisions = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalRequest
        fields = ["id", "process_id", "entity_id", "record_id", "status",
                  "current_level", "requested_by", "resolved_by", "resolved_at",
                  "resolution_comment", "workflow_run_id", "step_run_id", "expires_at",
                  "created_at", "updated_at", "decisions"]
        read_only_fields = fields

    def get_decisions(self, obj):
        qs = ApprovalDecision.objects.filter(request_id=obj.id).order_by("level", "decided_at")
        return ApprovalDecisionSerializer(qs, many=True).data
