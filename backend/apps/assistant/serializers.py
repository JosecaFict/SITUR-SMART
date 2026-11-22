import os

from rest_framework import serializers

MAX_MESSAGE_LENGTH = 1000
# Solo los ultimos mensajes viajan al proveedor: el historial completo gastaria
# cuota en cada pedido sin mejorar mucho la respuesta.
MAX_HISTORY = 16
MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB, ~5 min de voz comprimida
ALLOWED_AUDIO_EXTENSIONS = {".webm", ".ogg", ".mp3", ".m4a", ".mp4", ".wav", ".flac", ".aac"}


class HistoryItemSerializer(serializers.Serializer):
    rol = serializers.ChoiceField(choices=("usuario", "asistente"))
    contenido = serializers.CharField(max_length=4000, trim_whitespace=True)


class ChatRequestSerializer(serializers.Serializer):
    mensaje = serializers.CharField(max_length=MAX_MESSAGE_LENGTH, trim_whitespace=True)
    historial = HistoryItemSerializer(many=True, required=False, default=list)

    def validate_historial(self, value):
        return value[-MAX_HISTORY:]


class ContactSerializer(serializers.Serializer):
    """Contacto de la empresa; ``whatsapp_url`` solo si el telefono es celular."""

    telefono = serializers.CharField(allow_null=True)
    whatsapp = serializers.BooleanField()
    whatsapp_url = serializers.CharField(allow_null=True)
    email = serializers.CharField(allow_null=True)


class LodgingCardSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    tipo = serializers.CharField()
    ciudad = serializers.CharField()
    localidad = serializers.CharField(allow_null=True)
    empresa = serializers.CharField()
    estrellas = serializers.IntegerField(allow_null=True)
    precio_desde = serializers.CharField(allow_null=True)
    moneda = serializers.CharField()
    servicios = serializers.ListField(child=serializers.CharField())
    imagen_url = serializers.CharField(allow_null=True)
    url = serializers.CharField()
    puntaje = serializers.IntegerField(required=False)
    motivos = serializers.ListField(child=serializers.CharField(), required=False)
    contacto = ContactSerializer(allow_null=True, required=False)


class GeneratedReportSerializer(serializers.Serializer):
    """Reporte que el asistente armo para el personal; la web baja el archivo."""

    tipo = serializers.CharField()
    titulo = serializers.CharField()
    formato = serializers.ChoiceField(choices=("pdf", "excel"), allow_null=True)
    desde = serializers.DateField(allow_null=True)
    hasta = serializers.DateField(allow_null=True)
    empresa_id = serializers.IntegerField(allow_null=True)
    empresa = serializers.CharField(allow_null=True)
    filas = serializers.IntegerField()


class TourCardSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    tipo = serializers.CharField()
    ciudad = serializers.CharField()
    localidad = serializers.CharField(allow_null=True)
    empresa = serializers.CharField()
    precio_por_persona = serializers.CharField()
    moneda = serializers.CharField()
    duracion = serializers.CharField(allow_null=True)
    dificultad = serializers.CharField(allow_null=True)
    edad_minima = serializers.IntegerField(allow_null=True)
    idioma = serializers.CharField(allow_null=True)
    proxima_salida = serializers.CharField(allow_null=True)
    salidas_disponibles = serializers.IntegerField(allow_null=True)
    imagen_url = serializers.CharField(allow_null=True)
    url = serializers.CharField()
    contacto = ContactSerializer(allow_null=True, required=False)


class PromotionCardSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    empresa = serializers.CharField()
    modalidad = serializers.CharField()
    descuento_porcentaje = serializers.CharField()
    precio_original = serializers.CharField(allow_null=True)
    precio_final = serializers.CharField(allow_null=True)
    moneda = serializers.CharField(allow_null=True)
    incluye = serializers.ListField(child=serializers.CharField())
    ciudades = serializers.ListField(child=serializers.CharField())
    vence = serializers.CharField(allow_null=True)
    se_puede_reservar = serializers.BooleanField()
    imagen_url = serializers.CharField(allow_null=True)
    url = serializers.CharField()


class ChatResponseSerializer(serializers.Serializer):
    respuesta = serializers.CharField()
    hospedajes = LodgingCardSerializer(many=True)
    tours = TourCardSerializer(many=True)
    promociones = PromotionCardSerializer(many=True)
    reportes = GeneratedReportSerializer(many=True)


class VoiceRequestSerializer(serializers.Serializer):
    audio = serializers.FileField()

    def validate_audio(self, value):
        if value.size > MAX_AUDIO_BYTES:
            raise serializers.ValidationError("El audio es demasiado largo. Máximo 10 MB.")
        ext = os.path.splitext(value.name or "")[1].lower()
        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            raise serializers.ValidationError(
                f"Formato de audio no permitido ({ext or 'sin extensión'}). "
                f"Formatos aceptados: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}."
            )
        return value


class VoiceResponseSerializer(serializers.Serializer):
    texto = serializers.CharField(allow_blank=True)


class StatusResponseSerializer(serializers.Serializer):
    chat = serializers.BooleanField()
    voz = serializers.BooleanField()


class RecommendationQuerySerializer(serializers.Serializer):
    ciudad_id = serializers.IntegerField(min_value=1, required=False)
    ciudad = serializers.CharField(max_length=80, required=False)
    presupuesto = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=1, required=False)
    huespedes = serializers.IntegerField(min_value=1, max_value=100, required=False)
    estrellas = serializers.IntegerField(min_value=1, max_value=5, required=False)
    servicios = serializers.CharField(
        max_length=200, required=False, help_text="Separados por coma, ej. wifi,desayuno"
    )
    limite = serializers.IntegerField(min_value=1, max_value=10, required=False, default=5)
