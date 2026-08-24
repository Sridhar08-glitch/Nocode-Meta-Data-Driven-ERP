"""Serializers for the portal authentication realm."""
from rest_framework import serializers


class PortalLoginSerializer(serializers.Serializer):
    workspace_slug = serializers.SlugField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class PortalRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()
