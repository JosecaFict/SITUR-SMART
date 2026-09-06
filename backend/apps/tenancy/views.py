from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import City, Country
from .serializers import (
    CitySerializer,
    CompanyCreateSerializer,
    CompanySelfSignupSerializer,
    CompanySerializer,
    CompanyUpdateSerializer,
    CountrySerializer,
    OwnerAssignSerializer,
    PlanSerializer,
    SubscriptionChangeSerializer,
    SubscriptionSerializer,
)
from .services import (
    assign_company_owner,
    change_company_subscription,
    create_company,
    get_company,
    get_company_subscription,
    get_subscription_usage,
    list_companies,
    list_plans,
    require_company_management,
    self_signup_company,
    update_company,
)


class CountryListView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(responses=CountrySerializer(many=True))
    def get(self, request):
        return Response(CountrySerializer(Country.objects.all(), many=True).data)


class CityListView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(responses=CitySerializer(many=True))
    def get(self, request):
        queryset = City.objects.select_related("country")
        country_id = request.query_params.get("pais")
        if country_id:
            queryset = queryset.filter(country_id=country_id)
        return Response(CitySerializer(queryset, many=True).data)


class CompanyListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=CompanySerializer(many=True))
    def get(self, request):
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


class CompanySignupView(APIView):
    permission_classes = (AllowAny,)

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
        serializer = SubscriptionChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = change_company_subscription(
            actor=request.user,
            company_id=pk,
            request=request,
            **serializer.validated_data,
        )
        return Response(SubscriptionSerializer(subscription).data)
