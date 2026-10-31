from rest_framework import serializers

from .models import ProductReview


class ReviewWriteSerializer(serializers.Serializer):
    calificacion = serializers.IntegerField(min_value=1, max_value=5)
    comentario = serializers.CharField(allow_blank=False, trim_whitespace=True)


class ReviewSerializer(serializers.ModelSerializer):
    producto_id = serializers.IntegerField(source="product_id", read_only=True)
    autor = serializers.SerializerMethodField()
    es_propia = serializers.SerializerMethodField()
    calificacion = serializers.IntegerField(source="rating", read_only=True)
    comentario = serializers.CharField(source="comment", read_only=True)
    creado_en = serializers.DateTimeField(source="created_at", read_only=True)
    actualizado_en = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = ProductReview
        fields = (
            "id", "producto_id", "autor", "es_propia", "calificacion",
            "comentario", "creado_en", "actualizado_en",
        )

    def get_autor(self, review) -> str:
        # El correo y otros datos privados nunca forman parte de la respuesta.
        return review.user.first_names

    def get_es_propia(self, review) -> bool:
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and review.user_id == request.user.id)
