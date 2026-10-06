import '../../../core/network/api_client.dart';

/// Hospedaje recomendado dentro de una respuesta del asistente.
class AssistantLodging {
  const AssistantLodging({
    required this.id,
    required this.nombre,
    required this.tipo,
    required this.ciudad,
    required this.moneda,
    this.localidad,
    this.estrellas,
    this.precioDesde,
    this.imagenUrl,
    this.motivos = const [],
  });

  /// Id de establecimiento: abre /hospedaje/{id}.
  final int id;
  final String nombre;
  final String tipo;
  final String ciudad;
  final String moneda;
  final String? localidad;
  final int? estrellas;
  final String? precioDesde;
  final String? imagenUrl;
  final List<String> motivos;

  factory AssistantLodging.fromJson(Map<String, dynamic> json) => AssistantLodging(
        id: json['id'] is int ? json['id'] as int : int.tryParse('${json['id']}') ?? 0,
        nombre: json['nombre']?.toString() ?? '',
        tipo: json['tipo']?.toString() ?? '',
        ciudad: json['ciudad']?.toString() ?? '',
        moneda: json['moneda']?.toString() ?? '',
        localidad: json['localidad']?.toString(),
        estrellas: json['estrellas'] is int ? json['estrellas'] as int : null,
        precioDesde: json['precio_desde']?.toString(),
        imagenUrl: json['imagen_url']?.toString(),
        motivos: [for (final motivo in json['motivos'] as List<dynamic>? ?? const []) motivo.toString()],
      );
}

class AssistantReply {
  const AssistantReply({required this.texto, required this.hospedajes});

  final String texto;
  final List<AssistantLodging> hospedajes;
}

class AssistantStatus {
  const AssistantStatus({required this.chat, required this.voz});

  final bool chat;
  final bool voz;
}

/// Mensaje de la conversación tal como viaja en el historial.
class ChatTurn {
  const ChatTurn({required this.rol, required this.contenido});

  /// "usuario" o "asistente".
  final String rol;
  final String contenido;

  Map<String, String> toJson() => {'rol': rol, 'contenido': contenido};
}

/// Asistente virtual IA (asistente/*). El chat y la voz requieren sesión.
class AssistantService {
  AssistantService({ApiClient? apiClient}) : _api = apiClient ?? ApiClient();

  /// El backend recorta igual a 10; mandar más solo gasta datos.
  static const int historyLimit = 10;

  final ApiClient _api;

  /// Si el backend no tiene proveedor de IA configurado, el chat no se ofrece.
  Future<AssistantStatus> status() async {
    final data = await _api.getPublic('asistente/estado/');
    final map = data is Map<String, dynamic> ? data : const <String, dynamic>{};
    return AssistantStatus(chat: map['chat'] == true, voz: map['voz'] == true);
  }

  Future<AssistantReply> chat(String mensaje, List<ChatTurn> historial) async {
    final recent = historial.length > historyLimit
        ? historial.sublist(historial.length - historyLimit)
        : historial;
    final data = await _api.postAuth('asistente/chat/', {
      'mensaje': mensaje,
      'historial': [for (final turn in recent) turn.toJson()],
    });
    return AssistantReply(
      texto: plainText(data['respuesta']?.toString() ?? ''),
      hospedajes: [
        for (final item in data['hospedajes'] as List<dynamic>? ?? const [])
          if (item is Map<String, dynamic>) AssistantLodging.fromJson(item),
      ],
    );
  }

  /// Transcribe una nota de voz. El texto se muestra antes de enviarlo para
  /// que el turista pueda corregirlo.
  Future<String> transcribe(String audioPath) async {
    final data = await _api.postFileAuth('asistente/voz/', field: 'audio', filePath: audioPath);
    return data['texto']?.toString().trim() ?? '';
  }

  /// El modelo a veces responde con Markdown; en una burbuja de chat los
  /// asteriscos y almohadillas solo estorban.
  /// Mismas reglas que el chat web.
  static String plainText(String text) => text
      .replaceAllMapped(RegExp(r'\*\*(.+?)\*\*'), (match) => match[1]!)
      .replaceAll(RegExp(r'^#{1,6}\s+', multiLine: true), '')
      .replaceAll(RegExp(r'^\s*[*-]\s+', multiLine: true), '• ')
      .trim();
}
