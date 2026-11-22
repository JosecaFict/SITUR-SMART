from django.conf import settings
from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import brevo
from apps.bookings.models import Booking
from apps.catalog.models import Availability
from apps.rbac.models import Role
from apps.rbac.views import tenant_id_from_request
from apps.tenancy.models import Tenant

from . import campaigns, communications, marketing, push
from .models import Communication, Notification

CONTEXT_PARAMETER = OpenApiParameter("X-Tenant-ID", int, OpenApiParameter.HEADER,
                                     description="Empresa activa; omitir solo para alcance global SuperAdmin.")


class AudienceSerializer(serializers.Serializer):
    grupo = serializers.ChoiceField(choices=sorted(communications.GROUPS), default="TODOS")
    empresa_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=500, default=list)
    rol_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=500, default=list)
    usuario_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=10000, default=list)
    reserva_id = serializers.IntegerField(min_value=1, required=False)
    salida_id = serializers.IntegerField(min_value=1, required=False)


class CommunicationSerializer(serializers.Serializer):
    titulo = serializers.CharField(max_length=150)
    mensaje = serializers.CharField(max_length=10000)
    tipo = serializers.ChoiceField(choices=Communication.Kind.choices)
    audiencia = AudienceSerializer()
    reserva_id = serializers.IntegerField(min_value=1, allow_null=True, default=None)
    programado_en = serializers.DateTimeField(allow_null=True, default=None)
    vence_en = serializers.DateTimeField(allow_null=True, default=None)
    promocion_id = serializers.IntegerField(min_value=1, allow_null=True, default=None)
    enviar_correo = serializers.BooleanField(read_only=True)


class CommunicationOutputSerializer(CommunicationSerializer):
    id = serializers.IntegerField()
    estado = serializers.ChoiceField(choices=Communication.State.choices)
    remitente = serializers.CharField()
    creado_en = serializers.DateTimeField()
    publicado_en = serializers.DateTimeField(allow_null=True)
    total_destinatarios = serializers.IntegerField()
    leidas = serializers.IntegerField()
    push_pendientes = serializers.IntegerField()
    push_aceptados = serializers.IntegerField()
    push_fallidos = serializers.IntegerField()
    sin_dispositivo = serializers.IntegerField()
    programados = serializers.IntegerField()
    omitidos = serializers.IntegerField()
    error_envio = serializers.CharField(allow_blank=True)
    vencida = serializers.BooleanField()
    correos_pendientes = serializers.IntegerField()
    correos_aceptados = serializers.IntegerField()
    correos_fallidos = serializers.IntegerField()
    correos_omitidos = serializers.IntegerField()
    correos_revision = serializers.IntegerField()


class CommunicationPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = CommunicationOutputSerializer(many=True)
    resumen = serializers.DictField(child=serializers.IntegerField())


class RecipientSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    email = serializers.EmailField()


class AudiencePreviewSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    huella = serializers.CharField()
    destinatarios = RecipientSerializer(many=True)
    excluidos_promociones = serializers.IntegerField()


class OptionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class RoleOptionSerializer(OptionSerializer):
    codigo = serializers.CharField()
    ambito = serializers.CharField()
    empresa_id = serializers.IntegerField(allow_null=True)


class CommunicationOptionsSerializer(serializers.Serializer):
    es_global = serializers.BooleanField()
    empresas = OptionSerializer(many=True)
    roles = RoleOptionSerializer(many=True)
    usuarios = RecipientSerializer(many=True)
    usuarios_limitados = serializers.BooleanField()
    reservas = OptionSerializer(many=True)
    salidas = OptionSerializer(many=True)
    promociones = OptionSerializer(many=True)
    correo_disponible = serializers.BooleanField()


class PublishSerializer(serializers.Serializer):
    huella = serializers.CharField(min_length=64, max_length=64)


class EmailPreviewSerializer(serializers.Serializer):
    asunto = serializers.CharField()
    html = serializers.CharField()
    texto = serializers.CharField()


class CommunicationEmailPreviewView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(parameters=[CONTEXT_PARAMETER], responses=EmailPreviewSerializer)
    def get(self, request, pk):
        from .email_content import build_email, personalize
        item = communications.get(request.user, tenant_id_from_request(request), pk)
        sender = item.sender_name or (item.tenant.trade_name if item.tenant_id else "SITUR-SMART")
        item.sender_name = sender
        notice = Notification(title=personalize(item.title, request.user, sender),
                              message=personalize(item.message, request.user, sender))
        try:
            content = build_email(item, notice, request.user, preview=True)
        except ValueError:
            raise serializers.ValidationError("La dirección pública de la web aún no está configurada para correo.") from None
        return Response({"asunto": content["subject"], "html": content["html"], "texto": content["text"]})


class PushConfigSerializer(serializers.Serializer):
    habilitado = serializers.BooleanField()
    firebase = serializers.DictField(child=serializers.CharField())
    vapid_key = serializers.CharField(allow_blank=True)





def validated(data):
    serializer = CommunicationSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    # Una publicación siempre incluye bandeja, push y correo. El campo de salida
    # conserva el historial de publicaciones antiguas, pero no es un selector.
    return {**serializer.validated_data, "enviar_correo": True}


class CommunicationsPagination(PageNumberPagination):
    page_size = 20


class CommunicationsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(operation_id="communications_list", parameters=[CONTEXT_PARAMETER], responses=CommunicationPageSerializer)
    def get(self, request):
        tenant_id = tenant_id_from_request(request)
        items = communications.scoped(request.user, tenant_id)
        summary = dict(items.values("state").annotate(total=Count("pk")).values_list("state", "total"))
        state = request.query_params.get("estado")
        if state:
            items = items.filter(state=state)
        search = request.query_params.get("buscar", "").strip()[:100]
        if search:
            items = items.filter(Q(title__icontains=search) | Q(message__icontains=search))
        paginator = CommunicationsPagination()
        page = paginator.paginate_queryset(items, request, view=self)
        response = paginator.get_paginated_response([communications.as_dict(item) for item in page])
        response.data["resumen"] = summary
        return response

    @extend_schema(parameters=[CONTEXT_PARAMETER], request=CommunicationSerializer, responses={201: CommunicationOutputSerializer})
    def post(self, request):
        item = communications.save(request.user, tenant_id_from_request(request), validated(request.data), request=request)
        return Response(communications.as_dict(item), status=status.HTTP_201_CREATED)


class CommunicationDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(parameters=[CONTEXT_PARAMETER], responses=CommunicationOutputSerializer)
    def get(self, request, pk):
        return Response(communications.as_dict(communications.get(request.user, tenant_id_from_request(request), pk)))

    @extend_schema(parameters=[CONTEXT_PARAMETER], request=CommunicationSerializer, responses=CommunicationOutputSerializer)
    def patch(self, request, pk):
        tenant_id = tenant_id_from_request(request)
        existing = communications.get(request.user, tenant_id, pk)
        data = {**communications.payload_for(existing), **request.data}
        item = communications.save(request.user, tenant_id, validated(data), communication_id=pk, request=request)
        return Response(communications.as_dict(item))


class CommunicationAudienceView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(parameters=[CONTEXT_PARAMETER], request=CommunicationSerializer, responses=AudiencePreviewSerializer)
    def post(self, request):
        return Response(communications.preview(request.user, tenant_id_from_request(request), validated(request.data)))


class PublishCommunicationView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(parameters=[CONTEXT_PARAMETER], request=PublishSerializer, responses=CommunicationOutputSerializer)
    def post(self, request, pk):
        serializer = PublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fingerprint = serializer.validated_data["huella"]
        item = communications.publish(request.user, tenant_id_from_request(request), pk, fingerprint, request=request)
        return Response(communications.as_dict(item))


class CancelCommunicationView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(parameters=[CONTEXT_PARAMETER], request=None, responses=CommunicationOutputSerializer)
    def post(self, request, pk):
        return Response(communications.as_dict(campaigns.cancel(request.user, tenant_id_from_request(request), pk, request)))


class PreferenceInputSerializer(serializers.Serializer):
    empresa_id = serializers.IntegerField(min_value=1, allow_null=True)
    promociones = serializers.BooleanField()


class PreferenceItemSerializer(PreferenceInputSerializer):
    nombre = serializers.CharField()


class PreferenceOutputSerializer(serializers.Serializer):
    preferencias = PreferenceItemSerializer(many=True)
    limites = serializers.DictField(child=serializers.IntegerField())


class CommunicationPreferencesView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=PreferenceOutputSerializer)
    def get(self, request):
        return Response(marketing.preferences_for(request.user))

    @extend_schema(request=PreferenceInputSerializer, responses=PreferenceOutputSerializer)
    def patch(self, request):
        serializer = PreferenceInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return Response(marketing.set_preference(request.user, data["empresa_id"], data["promociones"]))


class CommunicationOptionsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(parameters=[CONTEXT_PARAMETER, OpenApiParameter("buscar", str)], responses=CommunicationOptionsSerializer)
    def get(self, request):
        tenant_id = tenant_id_from_request(request)
        communications.authorize(request.user, tenant_id)
        def query_ids(name):
            value = request.query_params.get(name, "")
            return value.split(",") if value else []
        criteria = AudienceSerializer(data={
            "grupo": request.query_params.get("grupo", "TODOS"),
            "empresa_ids": query_ids("empresa_ids"), "rol_ids": query_ids("rol_ids"),
        })
        criteria.is_valid(raise_exception=True)
        audience = criteria.validated_data
        kind = serializers.ChoiceField(choices=Communication.Kind.choices).run_validation(request.query_params.get("tipo", "OPERATIVA"))
        options_audience = {**audience, "grupo": "TODOS" if audience["grupo"] == "USUARIOS" else audience["grupo"]}
        users = communications.resolve(request.user, tenant_id, {"audiencia": options_audience, "tipo": kind})
        company_ids = [tenant_id] if tenant_id is not None else audience["empresa_ids"]
        companies = Tenant.objects.all()
        roles = Role.objects.all()
        if tenant_id is not None:
            companies = companies.filter(pk=tenant_id)
            roles = roles.filter(scope=Role.Scope.TENANT).filter(Q(tenant_id=tenant_id) | Q(tenant_id__isnull=True))
        if company_ids:
            roles = roles.filter(scope=Role.Scope.TENANT).filter(Q(tenant_id__isnull=True) | Q(tenant_id__in=company_ids))
        search = request.query_params.get("buscar", "").strip()[:100]
        bookings = Booking.objects.filter(status__in=communications.CUSTOMER_STATES).select_related("order__customer__user")
        departures = Availability.objects.filter(product__product_type__code__in=("TOUR", "EXPERIENCIA")).select_related("product")
        if company_ids:
            bookings = bookings.filter(tenant_id__in=company_ids)
            departures = departures.filter(tenant_id__in=company_ids)
        if search:
            users = users.filter(Q(email__icontains=search) | Q(first_names__icontains=search) | Q(last_names__icontains=search))
            bookings = bookings.filter(Q(code__icontains=search) | Q(order__customer__user__first_names__icontains=search)
                                       | Q(order__customer__user__last_names__icontains=search))
            departures = departures.filter(product__name__icontains=search)
        from django.utils import timezone

        from apps.promotions.models import Promotion
        promotions = Promotion.objects.filter(administrative_status="HABILITADA", ends_at__gt=timezone.now(),
                                               tenant__status="ACTIVO")
        if company_ids:
            promotions = promotions.filter(tenant_id__in=company_ids)
        if search:
            promotions = promotions.filter(name__icontains=search)
        return Response({
            "es_global": tenant_id is None,
            "empresas": [{"id": c.id, "nombre": c.trade_name} for c in companies[:500]],
            "roles": [{"id": r.id, "nombre": r.name, "codigo": r.code, "ambito": r.scope, "empresa_id": r.tenant_id} for r in roles[:500]],
            "usuarios": [{"id": u.id, "nombre": u.get_full_name(), "email": u.email} for u in users[:100]],
            "usuarios_limitados": users.count() > 100,
            "reservas": [{"id": b.id, "nombre": f"{b.code} · {b.order.customer.user.get_full_name()}"}
                         for b in bookings.order_by("-created_at")[:100]],
            "salidas": [{"id": d.id, "nombre": f"{d.product.name} · {d.start.isoformat()}"}
                        for d in departures.order_by("-start")[:100]],
            "promociones": [{"id": p.id, "nombre": p.name} for p in promotions[:100]],
            "correo_disponible": brevo.is_configured(),
        })


class WebPushConfigView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(responses=PushConfigSerializer)
    def get(self, request):
        firebase = {key: getattr(settings, name, "") for key, name in {
            "apiKey": "FIREBASE_WEB_API_KEY", "authDomain": "FIREBASE_WEB_AUTH_DOMAIN",
            "projectId": "FIREBASE_WEB_PROJECT_ID", "messagingSenderId": "FIREBASE_WEB_MESSAGING_SENDER_ID",
            "appId": "FIREBASE_WEB_APP_ID",
        }.items()}
        vapid = getattr(settings, "FIREBASE_WEB_VAPID_KEY", "")
        enabled = bool(all(firebase.values()) and vapid and push.is_configured())
        return Response({"habilitado": enabled, "firebase": firebase if enabled else {}, "vapid_key": vapid if enabled else ""})
