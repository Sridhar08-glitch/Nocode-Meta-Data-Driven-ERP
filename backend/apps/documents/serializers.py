"""DRF serializers for the documents API."""
from rest_framework import serializers

from .models import Document, DocumentFolder, DocumentVersion


class DocumentFolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentFolder
        fields = ["id", "name", "parent_id", "path", "is_system", "created_at", "updated_at"]
        read_only_fields = ["id", "path", "is_system", "created_at", "updated_at"]


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "folder_id", "name", "description", "mime_type", "extension",
                  "size_bytes", "storage_backend", "checksum_sha256", "status",
                  "av_scanned_at", "av_clean", "current_version", "is_latest",
                  "entity_id", "record_id", "is_public", "created_at", "updated_at"]
        read_only_fields = [f for f in fields if f not in ("name", "description",
                                                           "folder_id", "is_public")]
        # NB: storage_key is intentionally never serialised.


class DocumentVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentVersion
        fields = ["id", "document_id", "version_number", "size_bytes",
                  "checksum_sha256", "uploaded_by", "comment", "created_at"]
        read_only_fields = fields
