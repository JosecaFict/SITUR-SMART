from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.rbac.views import tenant_id_from_request

from . import llm, services
from .recommendations import Criteria, recommend
from .serializers import (
    ChatRequestSerializer,
    ChatResponseSerializer,
    LodgingCardSerializer,
    RecommendationQuerySerializer,
    StatusResponseSerializer,
    VoiceRequestSerializer,
    VoiceResponseSerializer,
)


class AssistantUnavailableError(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = (
        "El asistente virtual no está disponible en este momento. "
        "Puedes seguir buscando hospedajes en el Marketplace."
    )
    default_code = "asistente_no_disponible"


class AssistantBusyError(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = (
        "El asistente alcanzó su límite de uso por ahora. Inténtalo de nuevo en unos minutos."
    )
    default_code = "asistente_ocupado"


def _translate(exc: llm.AssistantUnavailable) -> APIException:
    return AssistantBusyError() if isinstance(exc, llm.AssistantRateLimited) else AssistantUnavailableError()


class AssistantThrottle(UserRateThrottle):
    """Limite por usuario: cada mensaje consume cuota del proveedor de IA.

    Igual que la geocodificacion, se apoya en la cache por omision (memoria
    del proceso): no es un limite global ni durable, pero alcanza para el piloto.
    """

    scope = "asistente"


class AssistantVoiceThrottle(UserRateThrottle):
    scope = "asistente_voz"


class AssistantStatusView(APIView):
    """Le dice al cliente si mostrar el chat y el boton de voz."""

    permission_classes = (AllowAny,)

    @extend_schema(responses=StatusResponseSerializer)
    def get(self, request):
        return Response({"chat": llm.is_configured(), "voz": llm.voice_configured()})


class AssistantChatView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (AssistantThrottle,)

    @extend_schema(request=ChatRequestSerializer, responses=ChatResponseSerializer)
    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = services.reply(
                message=data["mensaje"],
                history=data["historial"],
                user=request.user,
                tenant_id=tenant_id_from_request(request),
            )
        except llm.AssistantUnavailable as exc:
            raise _translate(exc) from exc
        return Response(result)


class AssistantVoiceView(APIView):
    """Transcribe un audio a texto. El texto luego se envia a /asistente/chat/.

    Se separa del chat a proposito: el cliente muestra lo que se entendio antes
    de enviarlo, y el usuario puede corregirlo si la transcripcion fallo.
    """

    permission_classes = (IsAuthenticated,)
    throttle_classes = (AssistantVoiceThrottle,)
    parser_classes = (MultiPartParser, FormParser)

    @extend_schema(request=VoiceRequestSerializer, responses=VoiceResponseSerializer)
    def post(self, request):
        serializer = VoiceRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        audio = serializer.validated_data["audio"]
        try:
            text = llm.transcribe(
                audio=audio.read(),
                filename=audio.name or "audio.webm",
                content_type=getattr(audio, "content_type", "") or "",
            )
        except llm.AssistantUnavailable as exc:
            raise _translate(exc) from exc
        return Response({"texto": text})


class RecommendationListView(APIView):
    """Recomendaciones por reglas, sin IA: funcionan aunque el proveedor caiga."""

    permission_classes = (AllowAny,)

    @extend_schema(parameters=[RecommendationQuerySerializer], responses=LodgingCardSerializer(many=True))
    def get(self, request):
        query = RecommendationQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        services_wanted = [s.strip() for s in data.get("servicios", "").split(",") if s.strip()]
        results = recommend(
            Criteria(
                ciudad=data.get("ciudad"),
                ciudad_id=data.get("ciudad_id"),
                presupuesto=data.get("presupuesto"),
                huespedes=data.get("huespedes"),
                estrellas=data.get("estrellas"),
                servicios=services_wanted[:6],
                limite=data["limite"],
            )
        )
        return Response(results)
