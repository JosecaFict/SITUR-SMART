import 'package:flutter/foundation.dart';

import '../../../core/network/api_client.dart';

class AppNotification {
  const AppNotification({
    required this.id,
    required this.kind,
    required this.title,
    required this.message,
    required this.read,
    required this.createdAt,
    this.bookingId,
    this.communicationId,
    this.sender,
    this.reason,
    this.communicationType,
    this.promotionId,
    this.expiresAt,
  });

  final int id;

  /// Tipo de aviso, incluyendo COMUNICACION.
  final String kind;
  final String title;
  final String message;
  final bool read;
  final DateTime createdAt;

  /// Reserva a la que lleva al tocarla.
  final int? bookingId;
  final int? communicationId;
  final String? sender;
  final String? reason;
  final String? communicationType;
  final int? promotionId;
  final DateTime? expiresAt;
  bool get expired => expiresAt != null && !expiresAt!.isAfter(DateTime.now());

  bool get isCommunication => kind == 'COMUNICACION';

  String get communicationTypeLabel => switch (communicationType) {
    'INTERNA' => 'Interna',
    'OPERATIVA' => 'Operativa',
    'PROMOCIONAL' => 'Promocional',
    _ => 'Comunicación',
  };

  AppNotification copyWith({bool? read}) => AppNotification(
    id: id,
    kind: kind,
    title: title,
    message: message,
    read: read ?? this.read,
    createdAt: createdAt,
    bookingId: bookingId,
    communicationId: communicationId,
    sender: sender,
    reason: reason,
    communicationType: communicationType,
    promotionId: promotionId,
    expiresAt: expiresAt,
  );

  factory AppNotification.fromJson(Map<String, dynamic> json) {
    final data = json['datos'] is Map<String, dynamic>
        ? json['datos'] as Map<String, dynamic>
        : const {};
    final booking = data['reserva_id'];
    return AppNotification(
      id: json['id'] is int
          ? json['id'] as int
          : int.tryParse('${json['id']}') ?? 0,
      kind: json['tipo']?.toString() ?? '',
      title: json['titulo']?.toString() ?? '',
      message: json['mensaje']?.toString() ?? '',
      read: json['leida'] == true,
      createdAt:
          DateTime.tryParse('${json['creado_en'] ?? ''}')?.toLocal() ??
          DateTime(1970),
      bookingId: booking is int ? booking : int.tryParse('${booking ?? ''}'),
      communicationId: int.tryParse('${data['comunicacion_id'] ?? ''}'),
      sender: data['remitente']?.toString(),
      reason: data['motivo']?.toString(),
      communicationType: data['tipo_comunicacion']?.toString(),
      promotionId: int.tryParse('${data['promocion_id'] ?? ''}'),
      expiresAt: DateTime.tryParse('${data['vence_en'] ?? ''}')?.toLocal(),
    );
  }
}

class NotificationsResult {
  const NotificationsResult({required this.items, required this.hasNext});

  final List<AppNotification> items;
  final bool hasNext;
}

/// Bandeja de avisos (me/notificaciones/).
class NotificationsService {
  NotificationsService({ApiClient? apiClient})
    : _api = apiClient ?? ApiClient();

  final ApiClient _api;

  Future<NotificationsResult> list({int page = 1}) async {
    final data = await _api.getMap('me/notificaciones/?page=$page', '');
    return NotificationsResult(
      items: (data['results'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(AppNotification.fromJson)
          .toList(),
      hasNext: data['next'] != null,
    );
  }

  Future<int> unreadCount() async {
    final data = await _api.getMap('me/notificaciones/no-leidas/', '');
    final value = data['no_leidas'];
    return value is int ? value : int.tryParse('$value') ?? 0;
  }

  Future<void> markRead(int id) =>
      _api.postAuth('me/notificaciones/$id/leer/', const {});

  Future<void> markAllRead() async {
    // Responde 204 sin cuerpo: postAuth espera un objeto, así que se usa la
    // variante que tolera respuestas vacías.
    await _api.postAuthEmpty('me/notificaciones/leer-todas/');
  }
}

/// Contador de no leídas que comparten la campana y la bandeja.
class NotificationsStore extends ChangeNotifier {
  NotificationsStore({NotificationsService? service})
    : _service = service ?? NotificationsService();

  static final NotificationsStore instance = NotificationsStore();

  final NotificationsService _service;
  int _unread = 0;

  int get unread => _unread;

  /// Consulta el contador. Si falla (sin red) se conserva el último valor.
  Future<void> refresh() async {
    try {
      _set(await _service.unreadCount());
    } catch (_) {}
  }

  void decrement() => _set(_unread > 0 ? _unread - 1 : 0);

  void clear() => _set(0);

  void _set(int value) {
    if (value == _unread) return;
    _unread = value;
    notifyListeners();
  }
}
