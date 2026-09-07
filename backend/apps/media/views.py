from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ImageUploadSerializer, MediaResponseSerializer
from .services import CloudinaryService


class MediaUploadView(APIView):
    """
    Endpoint para subida de imágenes a Cloudinary.
    Requiere autenticación de usuario.
    Optimiza la imagen y devuelve la URL segura para guardarla en el modelo correspondiente.
    """
    permission_classes = (IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    @extend_schema(
        request=ImageUploadSerializer,
        responses={201: MediaResponseSerializer},
        description="Sube un archivo de imagen (hasta 10 MB) a Cloudinary y devuelve la URL segura optimizada.",
    )
    def post(self, request):
        serializer = ImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_obj = serializer.validated_data["file"]
        folder = serializer.validated_data.get("folder", "productos")

        result = CloudinaryService.upload_image(file_obj=file_obj, folder=folder)

        return Response(result, status=status.HTTP_201_CREATED)
