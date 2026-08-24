from rest_framework import serializers

from .models import InstalledSolution, SolutionTemplate


class SolutionTemplateSerializer(serializers.ModelSerializer):
    summary = serializers.SerializerMethodField()

    class Meta:
        model = SolutionTemplate
        fields = ["id", "name", "slug", "category", "description", "publisher",
                  "icon", "color", "version", "is_system", "is_published",
                  "install_count", "summary", "created_at"]
        read_only_fields = ["id", "install_count", "created_at"]

    def get_summary(self, obj):
        m = obj.manifest or {}
        keys = ["entities", "forms", "views", "workflows", "rules", "reports",
                "roles", "dashboards", "applications"]
        return {k: len(m.get(k, []) or []) for k in keys}


class SolutionTemplateWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SolutionTemplate
        fields = ["name", "slug", "category", "description", "publisher",
                  "icon", "color", "version", "manifest"]


class InstalledSolutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstalledSolution
        fields = ["id", "solution_template_id", "solution_slug", "solution_name",
                  "installed_version", "status", "summary",
                  "created_entity_ids", "created_application_ids", "created_at"]
        read_only_fields = fields
