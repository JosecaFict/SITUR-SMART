from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.rbac.views import tenant_id_from_request

from . import subscriptions
from .models import City, Country
from .serializers import (
    AdminCitySerializer,
    AdminCountrySerializer,
    CatalogStatusSerializer,
    CitySerializer,
    CityWriteSerializer,
    CompanyCreateSerializer,
    CompanySelfSignupSerializer,
    CompanySerializer,
    CompanyStatusSerializer,
    CompanyUpdateSerializer,
    CountryCreateSerializer,
    CountrySerializer,
    CountryUpdateSerializer,
    OwnerAssignSerializer,
    PlanSerializer,
    SubscriptionChangeSerializer,
    SubscriptionSerializer,
)
from .services import (
    assign_company_owner,
    change_city_status,
    change_company_status,
    change_company_subscription,
    change_country_status,
    create_city,
    create_company,
    create_country,
    get_company,
    get_company_subscription,
    get_subscription_usage,
    list_admin_cities,
    list_admin_countries,
    list_companies,
    list_plans,
    require_company_management,
    require_location_management,
    require_subscription_management,
    self_signup_company,
    update_city,
    update_company,
    update_country,
)


class CountryListView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(responses=CountrySerializer(many=True))
    def get(self, request):
        return Response(CountrySerializer(Country.objects.filter(active=True), many=True).data)


class CityListView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(responses=CitySerializer(many=True))
    def get(self, request):
        queryset = City.objects.select_related("country").filter(active=True, country__active=True)
        country_id = request.query_params.get("pais")
        if country_id:
            queryset = queryset.filter(country_id=country_id)
        return Response(CitySerializer(queryset, many=True).data)


class AdminCountryListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        countries = list_admin_countries(
            actor=request.user,
            search=request.query_params.get("buscar", "").strip(),
            active=request.query_params.get("activo", "").strip().lower(),
        )
        return Response(AdminCountrySerializer(countries, many=True).data)

    def post(self, request):
        require_location_management(request.user)
        serializer = CountryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        country = create_country(actor=request.user, request=request, **serializer.validated_data)
        return Response(AdminCountrySerializer(country).data, status=status.HTTP_201_CREATED)


class AdminCountryDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def patch(self, request, pk):
        require_location_management(request.user)
        serializer = CountryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        country = update_country(actor=request.user, country_id=pk, request=request, **serializer.validated_data)
        return Response(AdminCountrySerializer(country).data)


class AdminCountryStatusView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, pk):
        require_location_management(request.user)
        serializer = CatalogStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        country = change_country_status(actor=request.user, country_id=pk, request=request, **serializer.validated_data)
        return Response(AdminCountrySerializer(country).data)


class AdminCityListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        country_id = request.query_params.get("pais")
        cities = list_admin_cities(
            actor=request.user,
            country_id=int(country_id) if country_id and country_id.isdigit() else None,
            search=request.query_params.get("buscar", "").strip(),
            active=request.query_params.get("activo", "").strip().lower(),
        )
        return Response(AdminCitySerializer(cities, many=True).data)

    def post(self, request):
        require_location_management(request.user)
        serializer = CityWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        city = create_city(actor=request.user, request=request, **serializer.validated_data)
        return Response(AdminCitySerializer(city).data, status=status.HTTP_201_CREATED)


class AdminCityDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def patch(self, request, pk):
        require_location_management(request.user)
        serializer = CityWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        city = update_city(actor=request.user, city_id=pk, request=request, **serializer.validated_data)
        return Response(AdminCitySerializer(city).data)


class AdminCityStatusView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, pk):
        require_location_management(request.user)
        serializer = CatalogStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        city = change_city_status(actor=request.user, city_id=pk, request=request, **serializer.validated_data)
        return Response(AdminCitySerializer(city).data)


class CompanyListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=CompanySerializer(many=True))
    def get(self, request):
        # Sin permiso de plataforma el servicio acota a las empresas propias, de
        # modo que este endpoint sirve a los dos publicos sin filtrar nada: no
        # se exige TENANTS_LEER aqui porque no tenerlo no es un error.
        companies = list_companies(
            actor=request.user,
            search=request.query_params.get("buscar", "").strip(),
            status=request.query_params.get("estado", "").strip(),
        )
        return Response(CompanySerializer(companies, many=True).data)

    @extend_schema(request=CompanyCreateSerializer, responses={201: CompanySerializer})
    def post(self, request):
        require_company_management(request.user)
        serializer = CompanyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = create_company(
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(CompanySerializer(company).data, status=status.HTTP_201_CREATED)


class CompanyDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=CompanySerializer)
    def get(self, request, pk):
        return Response(CompanySerializer(get_company(actor=request.user, company_id=pk)).data)

    @extend_schema(request=CompanyUpdateSerializer, responses=CompanySerializer)
    def patch(self, request, pk):
        require_company_management(request.user)
        serializer = CompanyUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        company = update_company(
            actor=request.user,
            company_id=pk,
            request=request,
            **serializer.validated_data,
        )
        return Response(CompanySerializer(company).data)


class CompanyStatusView(APIView):
    """Cambio de estado como accion propia, no como un campo mas del PATCH.

    Tiene reglas distintas de las de editar un dato: transiciones permitidas,
    requisitos para activar y su propia accion de bitacora. Un endpoint aparte
    deja eso explicito en el contrato y le permite al cliente distinguir "no
    pude guardar el nombre" de "esa transicion no existe".
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=CompanyStatusSerializer, responses=CompanySerializer)
    def post(self, request, pk):
        require_company_management(request.user)
        serializer = CompanyStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = change_company_status(
            actor=request.user,
            company_id=pk,
            request=request,
            **serializer.validated_data,
        )
        return Response(CompanySerializer(company).data)


class CompanyOwnerView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=OwnerAssignSerializer, responses=CompanySerializer)
    def put(self, request, pk):
        require_company_management(request.user)
        serializer = OwnerAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = assign_company_owner(
            actor=request.user,
            company_id=pk,
            request=request,
            **serializer.validated_data,
        )
        return Response(CompanySerializer(company).data)


class PlanListView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(responses=PlanSerializer(many=True))
    def get(self, request):
        return Response(PlanSerializer(list_plans(), many=True).data)


class SelfSignupThrottle(SimpleRateThrottle):
    """Tope por IP del autoregistro publico.

    Es el unico endpoint anonimo que crea empresa, usuario, rol y suscripcion de
    una sola llamada, asi que sin tope es una via para llenar el padron. Ahora
    las empresas nacen PENDIENTE y no llegan al Marketplace sin que la
    plataforma las active, pero el ruido en la base sigue siendo real.

    Mismo respaldo que el throttle de geocodificacion: la cache por omision de
    Django, memoria del proceso. **No es un limite global ni durable** -- se
    reinicia en cada despliegue y se multiplicaria por la cantidad de workers de
    gunicorn, que hoy es uno. No sustituye un captcha, que queda pendiente.
    """

    scope = "autoregistro"

    def get_cache_key(self, request, view):
        # El endpoint admite tanto visitantes como usuarios ya autenticados.
        # AnonRateThrottle dejaría sin límite al segundo grupo, aunque ambos
        # pueden crear exactamente las mismas filas. La cuota es por IP para
        # todos los llamadores.
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class CompanySignupView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (SelfSignupThrottle,)

    @extend_schema(request=CompanySelfSignupSerializer, responses={201: CompanySerializer})
    def post(self, request):
        serializer = CompanySelfSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company, subscription = self_signup_company(request=request, **serializer.validated_data)
        return Response(
            {
                "empresa": CompanySerializer(company).data,
                "suscripcion": SubscriptionSerializer(subscription).data,
            },
            status=status.HTTP_201_CREATED,
        )


class CompanySubscriptionView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=SubscriptionSerializer)
    def get(self, request, pk):
        subscription = get_company_subscription(actor=request.user, company_id=pk)
        return Response(
            {
                "suscripcion": SubscriptionSerializer(subscription).data if subscription else None,
                "uso": get_subscription_usage(tenant_id=pk),
            }
        )

    @extend_schema(request=SubscriptionChangeSerializer, responses=SubscriptionSerializer)
    def put(self, request, pk):
        # La vista tambien lo exige, no solo el servicio: antes este metodo no
        # comprobaba nada por si mismo y la autorizacion quedaba enteramente
        # dentro de la capa de servicio.
        require_subscription_management(request.user)
        serializer = SubscriptionChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = change_company_subscription(
            actor=request.user,
            company_id=pk,
            request=request,
            **serializer.validated_data,
        )
        return Response(SubscriptionSerializer(subscription).data)


class MyPlanSerializer(serializers.Serializer):
    renovacion_automatica = serializers.BooleanField()


class MyPlanPaySerializer(serializers.Serializer):
    plan_codigo = serializers.CharField(required=False, allow_blank=True, max_length=50)


class MyPlanView(APIView):
    """"Mi plan" de la empresa del encabezado X-Tenant-ID: vigencia, uso y pagos.

    Lo ve cualquier miembro, aun con la empresa restringida (justamente para
    enterarse). Cambiar la renovacion automatica es del propietario.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        return Response(subscriptions.plan_status(actor=request.user, tenant_id=tenant_id))

    @extend_schema(request=MyPlanSerializer, responses=OpenApiTypes.OBJECT)
    def patch(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = MyPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscriptions.set_auto_renew(
            actor=request.user,
            tenant_id=tenant_id,
            value=serializer.validated_data["renovacion_automatica"],
            request=request,
        )
        return Response(subscriptions.plan_status(actor=request.user, tenant_id=tenant_id))


class MyPlanPayView(APIView):
    """Abre el pago con Stripe de un periodo del plan actual o de otro plan."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=MyPlanPaySerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = MyPlanPaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        url = subscriptions.start_checkout(
            actor=request.user,
            tenant_id=tenant_id,
            plan_code=serializer.validated_data.get("plan_codigo") or None,
            request=request,
        )
        return Response({"checkout_url": url}, status=status.HTTP_201_CREATED)
