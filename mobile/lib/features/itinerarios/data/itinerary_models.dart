/// Itinerarios del turista (me/itinerarios/*).
library;

import '../../marketplace/models/marketplace_models.dart';

int? _int(Object? value) => value is int ? value : int.tryParse('${value ?? ''}');

String? _text(Object? value) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? null : text;
}

DateTime _day(Object? value) => DateTime.tryParse('${value ?? ''}') ?? DateTime(1970);

/// "2026-10-10" para la API.
String apiDate(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';

/// Un viaje en la lista de itinerarios.
class ItinerarySummary {
  const ItinerarySummary({
    required this.id,
    required this.name,
    required this.start,
    required this.end,
    required this.days,
    required this.activities,
    this.cityId,
    this.city,
    this.notes,
  });

  final int id;
  final String name;
  final int? cityId;
  final String? city;
  final DateTime start;
  final DateTime end;
  final String? notes;
  final int days;
  final int activities;

  /// Ya terminó: va abajo en la lista.
  bool get past => end.isBefore(DateTime.now().subtract(const Duration(days: 1)));

  factory ItinerarySummary.fromJson(Map<String, dynamic> json) => ItinerarySummary(
        id: _int(json['id']) ?? 0,
        name: json['nombre']?.toString() ?? '',
        cityId: _int(json['ciudad_id']),
        city: _text(json['ciudad']),
        start: _day(json['inicio']),
        end: _day(json['fin']),
        notes: _text(json['notas']),
        days: _int(json['dias']) ?? 1,
        activities: _int(json['actividades']) ?? 0,
      );
}

/// Algo del día: una actividad que cargó el turista o una reserva pagada.
class AgendaItem {
  const AgendaItem({
    required this.kind,
    required this.id,
    required this.title,
    this.time,
    this.note,
    this.product,
    this.bookingCode,
    this.moment,
    this.imageUrl,
    this.lodgingId,
    this.productId,
  });

  /// LIBRE o PRODUCTO (actividades) y RESERVA.
  final String kind;

  /// Id de la actividad, o de la reserva si [isBooking].
  final int id;
  final String title;

  /// "09:00" o null si no tiene hora.
  final String? time;
  final String? note;

  /// Producto del Marketplace de una actividad, si sigue publicado.
  final Product? product;

  final String? bookingCode;

  /// LLEGADA o SALIDA de un hospedaje; null en lo demás.
  final String? moment;
  final String? imageUrl;
  final int? lodgingId;
  final int? productId;

  bool get isBooking => kind == 'RESERVA';
  bool get isLodging => lodgingId != null;

  /// A dónde lleva al tocarlo, o null si no lleva a ningún lado.
  String? get route {
    if (isBooking) return '/reserva/$id';
    if (lodgingId != null) return '/hospedaje/$lodgingId';
    if (productId != null) return '/producto/$productId';
    return null;
  }

  factory AgendaItem.activity(Map<String, dynamic> json) {
    final product = json['producto'] is Map<String, dynamic>
        ? Product.fromJson(json['producto'] as Map<String, dynamic>)
        : null;
    return AgendaItem(
      kind: json['tipo']?.toString() ?? 'LIBRE',
      id: _int(json['id']) ?? 0,
      title: json['titulo']?.toString() ?? '',
      time: _text(json['hora']),
      note: _text(json['nota']),
      product: product,
      imageUrl: product?.imagenUrl,
      lodgingId: product?.hospedajeId,
      productId: product?.id,
    );
  }

  factory AgendaItem.booking(Map<String, dynamic> json) {
    final product = json['producto'] is Map<String, dynamic> ? json['producto'] as Map<String, dynamic> : const {};
    return AgendaItem(
      kind: 'RESERVA',
      id: _int(json['reserva_id']) ?? 0,
      title: json['titulo']?.toString() ?? '',
      bookingCode: _text(json['codigo']),
      moment: _text(json['momento']),
      imageUrl: _text(product['imagen_url']),
      lodgingId: _int(product['hospedaje_id']),
      productId: _int(product['id']),
    );
  }
}

class ItineraryDay {
  const ItineraryDay({required this.date, required this.bookings, required this.activities});

  final DateTime date;
  final List<AgendaItem> bookings;
  final List<AgendaItem> activities;

  bool get isEmpty => bookings.isEmpty && activities.isEmpty;

  /// Primero las reservas (no tienen hora) y después las actividades, que ya
  /// vienen ordenadas: sin hora primero y luego por hora.
  List<AgendaItem> get items => [...bookings, ...activities];

  factory ItineraryDay.fromJson(Map<String, dynamic> json) => ItineraryDay(
        date: _day(json['fecha']),
        bookings: (json['reservas'] as List<dynamic>? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(AgendaItem.booking)
            .toList(),
        activities: (json['actividades'] as List<dynamic>? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(AgendaItem.activity)
            .toList(),
      );
}

class ItineraryDetail {
  const ItineraryDetail({required this.summary, required this.agenda});

  final ItinerarySummary summary;
  final List<ItineraryDay> agenda;

  factory ItineraryDetail.fromJson(Map<String, dynamic> json) => ItineraryDetail(
        summary: ItinerarySummary.fromJson(json),
        agenda: (json['agenda'] as List<dynamic>? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(ItineraryDay.fromJson)
            .toList(),
      );
}
