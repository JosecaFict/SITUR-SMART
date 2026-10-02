import logging
from typing import Any, Dict
import cloudinary
import cloudinary.uploader
from django.conf import settings
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)


class CloudinaryService:
    """
    Servicio de integración con Cloudinary para subida, optimización
    y gestión de archivos multimedia en SITUR-SMART.
    """

    @classmethod
    def is_configured(cls) -> bool:
        """Verifica si las credenciales de Cloudinary están presentes."""
        cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "").strip()
        api_key = getattr(settings, "CLOUDINARY_API_KEY", "").strip()
        api_secret = getattr(settings, "CLOUDINARY_API_SECRET", "").strip()
        return bool(cloud_name and api_key and api_secret)

    @classmethod
    def _initialize(cls) -> None:
        """Configura el cliente de Cloudinary con las credenciales de entorno."""
        if not cls.is_configured():
            raise ValidationError(
                "El servicio de Cloudinary no está configurado en el servidor. "
                "Por favor defina CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY y CLOUDINARY_API_SECRET "
                "en las variables de entorno (.env)."
            )
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME.strip(),
            api_key=settings.CLOUDINARY_API_KEY.strip(),
            api_secret=settings.CLOUDINARY_API_SECRET.strip(),
            secure=True,
        )

    @classmethod
    def upload_image(
        cls,
        file_obj: Any,
        *,
        folder: str = "productos",
    ) -> Dict[str, Any]:
        """
        Sube una imagen a Cloudinary aplicando optimización automática de formato y calidad.

        :param file_obj: Archivo de imagen subido (UploadedFile o file-like object).
        :param folder: Subcarpeta lógica dentro de 'situr-smart/' (ej: 'productos', 'empresas', 'perfiles').
        :return: Diccionario con los metadatos de la imagen almacenada (url, public_id, format, etc.).
        """
        cls._initialize()

        clean_folder = folder.strip().lower().replace(" ", "_") if folder else "productos"
        target_folder = f"situr-smart/{clean_folder}"

        try:
            # Rebobinar el cursor del archivo si está abierto
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)

            upload_result = cloudinary.uploader.upload(
                file_obj,
                folder=target_folder,
                resource_type="image",
                transformation=[
                    {"quality": "auto", "fetch_format": "auto"}
                ],
            )

            return {
                "url": upload_result.get("secure_url", upload_result.get("url")),
                "public_id": upload_result.get("public_id"),
                "format": upload_result.get("format"),
                "bytes": upload_result.get("bytes"),
                "width": upload_result.get("width"),
                "height": upload_result.get("height"),
            }
        except ValidationError:
            raise
        except Exception as exc:
            logger.exception("Error al subir imagen a Cloudinary: %s", exc)
            raise ValidationError(f"Error al subir imagen a Cloudinary: {str(exc)}")

    @classmethod
    def delete_image(cls, public_id: str) -> bool:
        """
        Elimina un recurso de Cloudinary por su public_id.
        """
        if not cls.is_configured() or not public_id:
            return False

        cls._initialize()
        try:
            res = cloudinary.uploader.destroy(public_id, resource_type="image")
            return res.get("result") == "ok"
        except Exception as exc:
            logger.warning("No se pudo eliminar el recurso %s de Cloudinary: %s", public_id, exc)
            return False
