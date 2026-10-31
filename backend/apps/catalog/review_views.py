from django.db.models import Count
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ProductReview
from .review_serializers import ReviewSerializer, ReviewWriteSerializer
from .reviews import (
    create_review,
    delete_review,
    public_reviewable_product,
    update_review,
)


class ReviewPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


class ProductReviewListCreateView(APIView):
    permission_classes = (AllowAny,)

    def get_permissions(self):
        return [IsAuthenticated()] if self.request.method == "POST" else [AllowAny()]

    @extend_schema(responses=inline_serializer(
        name="ProductReviewPageResponse",
        fields={
            "count": serializers.IntegerField(),
            "next": serializers.CharField(allow_null=True),
            "previous": serializers.CharField(allow_null=True),
            "results": ReviewSerializer(many=True),
            "distribucion_calificaciones": serializers.DictField(child=serializers.IntegerField()),
        },
    ))
    def get(self, request, pk):
        public_reviewable_product(pk)
        reviews = ProductReview.objects.select_related("user").filter(product_id=pk)
        # Una consulta agrupada para todo el producto, independiente de la página.
        grouped = (
            ProductReview.objects.filter(product_id=pk)
            .order_by().values("rating").annotate(total=Count("id"))
        )
        distribution = {str(rating): 0 for rating in range(1, 6)}
        for row in grouped:
            distribution[str(row["rating"])] = row["total"]
        paginator = ReviewPagination()
        page = paginator.paginate_queryset(reviews, request, view=self)
        response = paginator.get_paginated_response(
            ReviewSerializer(page, many=True, context={"request": request}).data
        )
        response.data["distribucion_calificaciones"] = distribution
        return response

    @extend_schema(request=ReviewWriteSerializer, responses={201: ReviewSerializer})
    def post(self, request, pk):
        serializer = ReviewWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = create_review(
            user=request.user, product_id=pk,
            rating=serializer.validated_data["calificacion"],
            comment=serializer.validated_data["comentario"],
        )
        return Response(
            ReviewSerializer(review, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class OwnProductReviewView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={200: inline_serializer(
        name="OwnProductReviewResponse",
        fields={"resena": ReviewSerializer(allow_null=True)},
    )})
    def get(self, request, pk):
        public_reviewable_product(pk)
        review = ProductReview.objects.select_related("user").filter(
            product_id=pk, user=request.user
        ).first()
        return Response({
            "resena": ReviewSerializer(review, context={"request": request}).data if review else None
        })


class OwnReviewDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=ReviewWriteSerializer, responses=ReviewSerializer)
    def patch(self, request, pk):
        serializer = ReviewWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        changes = {}
        if "calificacion" in serializer.validated_data:
            changes["rating"] = serializer.validated_data["calificacion"]
        if "comentario" in serializer.validated_data:
            changes["comment"] = serializer.validated_data["comentario"]
        review = update_review(user=request.user, review_id=pk, **changes)
        return Response(ReviewSerializer(review, context={"request": request}).data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        delete_review(user=request.user, review_id=pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
