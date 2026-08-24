"""DRF serializers for the workflow API."""
from rest_framework import serializers

from .models import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowRun,
    WorkflowStep,
    WorkflowStepRun,
)


class WorkflowDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowDefinition
        fields = [
            "id", "name", "slug", "description", "trigger_type", "trigger_config",
            "entity_id", "module_id", "status", "version", "is_system",
            "max_concurrent_runs", "timeout_seconds", "retry_policy",
            "run_count", "error_count", "last_run_at", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "version", "is_system", "run_count", "error_count",
                            "last_run_at", "created_at", "updated_at"]


class WorkflowStepSerializer(serializers.ModelSerializer):
    # Accept every executor type (model choices list a subset; aliases like
    # "transform"/"nql_query" are valid executors too — validated against REGISTRY).
    step_type = serializers.CharField()

    class Meta:
        model = WorkflowStep
        fields = [
            "id", "workflow_id", "step_type", "name", "config",
            "position_x", "position_y", "is_entry", "on_error", "retry_config",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "workflow_id", "created_at", "updated_at"]

    def validate_step_type(self, value):
        from .executors import REGISTRY
        if value not in REGISTRY:
            raise serializers.ValidationError(f"Unknown step type {value!r}")
        return value


class WorkflowEdgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowEdge
        fields = ["id", "workflow_id", "source_step_id", "target_step_id",
                  "condition_label", "condition_expr"]
        read_only_fields = ["id", "workflow_id"]


class WorkflowStepRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowStepRun
        fields = ["id", "run_id", "step_id", "status", "started_at", "completed_at",
                  "duration_ms", "attempt_number", "input_data", "output_data",
                  "error_message"]


class WorkflowRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowRun
        fields = ["id", "workflow_id", "trigger_type", "trigger_payload", "entity_id",
                  "record_id", "status", "started_at", "completed_at", "duration_ms",
                  "error_message", "error_step_id", "context", "initiated_by",
                  "created_at", "updated_at"]
