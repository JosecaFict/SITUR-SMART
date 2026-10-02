import os
from rest_framework import serializers

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


class ImageUploadSerializer(serializers.Serializer):
    file = serializers.FileField(required=True, write_only=True)
    folder = serializers.CharField(
        max_length=60,
        required=False,
        default="productos",
        write_only=True,
    )

    def validate_file(self, value):
        # 1. Validar tamaño
        if value.size > MAX_FILE_SIZE_BYTES:
            raise serializers.ValidationError(
                f"El archivo es demasiado grande ({value.size // (1024 * 1024)} MB). "
                f"El tamaño máximo permitido es de 10 MB."
            )

        # 2. Validar extensión
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise serializers.ValidationError(
                f"Formato no permitido ({ext or 'sin extensión'}). "
                f"Formatos aceptados: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}."
            )

        # 3. Validar content_type si está disponible
        content_type = getattr(value, "content_type", "")
        if content_type and not (content_type.startswith("image/") or content_type == "application/octet-stream"):
            raise serializers.ValidationError("El archivo proporcionado no es una imagen válida.")

        return value


class MediaResponseSerializer(serializers.Serializer):
    url = serializers.URLField()
    public_id = serializers.CharField()
    format = serializers.CharField(required=False, allow_null=True)
    bytes = serializers.IntegerField(required=False, allow_null=True)
    width = serializers.IntegerField(required=False, allow_null=True)
    height = serializers.IntegerField(required=False, allow_null=True)
