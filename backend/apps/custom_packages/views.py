from django.http import HttpResponse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.serializers import ProductSerializer
from apps.catalog.views import MarketplacePagination

from . import purchase as purchases
from . import services
from .models import CustomPackage
from .purchase import create_purchase
from .receipt import build as build_receipt
from .serializers import (
    CatalogQuerySerializer,
    ComponentWriteSerializer,
    PackageCancellationSerializer,
    PackagePurchaseSerializer,
    PackageWriteSerializer,
)


class PackageCatalogView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        query = CatalogQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        values = query.validated_data
        products = services.catalog(city_id=values.get("ciudad"),
                                    product_type=values.get("tipo"), search=values.get("buscar"))
        paginator = MarketplacePagination()
        page = paginator.paginate_queryset(products, request, view=self)
        return paginator.get_paginated_response(ProductSerializer(page, many=True).data)


class PackageListView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        packages = CustomPackage.objects.filter(user=request.user).select_related("city").prefetch_related("components")
        return Response([services.package_data(package, detail=False) for package in packages])

    def post(self, request):
        serializer = PackageWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        package = services.create_package(request.user, serializer.validated_data)
        return Response(services.package_data(package), status=status.HTTP_201_CREATED)


class PackageDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, pk):
        return Response(services.package_data(services.owned_package(request.user, pk)))

    def patch(self, request, pk):
        package = services.owned_package(request.user, pk)
        serializer = PackageWriteSerializer(instance=package, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(services.package_data(services.update_package(request.user, pk, serializer.validated_data)))


class PackageComponentListView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, pk):
        serializer = ComponentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        package = services.add_component(request.user, pk, serializer.as_values())
        return Response(services.package_data(package), status=status.HTTP_201_CREATED)


class PackageComponentDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def patch(self, request, pk, component_id):
        serializer = ComponentWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        package = services.update_component(request.user, pk, component_id, serializer.as_values())
        return Response(services.package_data(package))

    def delete(self, request, pk, component_id):
        return Response(services.package_data(services.remove_component(request.user, pk, component_id)))


class PackageQuoteView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, pk):
        serializer = ComponentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        package = services.owned_package(request.user, pk)
        component_id = serializer.validated_data.get("componente_id")
        if component_id and not package.components.filter(id=component_id).exists():
            raise ValidationError({"componente_id": "El servicio no pertenece a este paquete."})
        quote = services._configuration(package, serializer.as_values(), exclude_id=component_id)
        return Response({"producto_id": quote.product.id, "precio_unitario": str(quote.unit_price),
                         "total": str(quote.total), "moneda_simbolo": quote.product.currency.symbol,
                         "disponible": True, "salida_id": quote.slot.id if quote.slot else None})


class PackageValidationView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, pk):
        save = request.data.get("guardar", False)
        if not isinstance(save, bool):
            raise ValidationError({"guardar": "Debe ser verdadero o falso."})
        return Response(services.package_data(services.validate_package(request.user, pk, save=save)))


class PackagePurchaseView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, pk):
        serializer = PackagePurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        purchase = create_purchase(
            user=request.user, package_id=pk,
            success_url=data["success_url"], cancel_url=data["cancel_url"],
            policies_accepted=data["acepta_politicas"],
            billing_name=data.get("razon_social_facturacion"),
            billing_tax_id=data.get("nit_facturacion"),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        return Response({
            "id": purchase.id, "estado": purchase.status,
            "total": str(purchase.final_amount),
            "checkout_url": getattr(purchase, "checkout_url", None),
            "reservas": list(purchase.allocations.values_list("booking_id", flat=True)),
        }, status=status.HTTP_201_CREATED)


class PackageCancellationView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, pk):
        return Response(purchases.cancellation_quote(user=request.user, purchase_id=pk))

    def post(self, request, pk):
        serializer = PackageCancellationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(purchases.cancel_purchase(
            user=request.user, purchase_id=pk,
            reason=serializer.validated_data["motivo"],
            idempotency_key=request.headers.get("Idempotency-Key"),
        ))


class PackageReceiptView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, pk):
        purchase = purchases.PackagePurchase.objects.select_related(
            "package", "order", "currency"
        ).filter(id=pk, package__user=request.user).first()
        if purchase is None:
            raise ValidationError("Compra de paquete no encontrada.")
        if purchase.status not in (
            purchases.PackagePurchase.Status.CONFIRMED,
            purchases.PackagePurchase.Status.REFUNDED,
        ):
            raise ValidationError("El comprobante estará disponible después de confirmar el pago.")
        response = HttpResponse(build_receipt(purchase), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="paquete-{purchase.id}.pdf"'
        return response
