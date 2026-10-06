/// Reservas del turista (me/reservas/*).
library;

/// Tipos de producto que se reservan. Un hotel no: se reservan sus habitaciones.
const bookableTypes = {'HABITACION', 'TOUR', 'EXPERIENCIA', 'ATRACCION', 'RESTAURANTE', 'PAQUETE'};

String _date(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';

int? _int(Object? value) => value is int ? value : int.tryParse('${value ?? ''}');

/// Lo que el turista pide: igual para cotizar y para reservar.
class BookingRequest {
  const BookingRequest({
    required this.productId,
    required this.start,
    required this.quantity,
    this.end,
    this.guests,
  });

  final int productId;
  final DateTime start;

  /// Salida, solo en habitaciones.
  final DateTime? end;

  /// Habitaciones en un hospedaje; personas en lo demás.
  final int quantity;
  final int? guests;

  Map<String, dynamic> toJson() => {
        'producto_id': productId,
        'fecha_inicio': _date(start),
        if (end != null) 'fecha_fin': _date(end!),
        'cantidad': quantity,
        if (guests != null) 'huespedes': guests,
      };
}

class BookingQuote {
  const BookingQuote({
    required this.total,
    required this.unitPrice,
    required this.currencySymbol,
    required this.available,
    required this.remaining,
    this.nights,
  });

  final String total;
  final String unitPrice;
  final String currencySymbol;
  final bool available;
  final int remaining;
  final int? nights;

  factory BookingQuote.fromJson(Map<String, dynamic> json) => BookingQuote(
        total: json['total']?.toString() ?? '0.00',
        unitPrice: json['precio_unitario']?.toString() ?? '0.00',
        currencySymbol: json['moneda_simbolo']?.toString() ?? '',
        available: json['disponible'] == true,
        remaining: _int(json['disponibles']) ?? 0,
        nights: _int(json['noches']),
      );
}

class Booking {
  const Booking({
    required this.id,
    required this.code,
    required this.status,
    required this.statusLabel,
    required this.company,
    required this.productId,
    required this.productName,
    required this.productType,
    required this.city,
    required this.start,
    required this.end,
    required this.quantity,
    required this.unit,
    required this.total,
    required this.currencySymbol,
    required this.createdAt,
    this.isLodging = false,
    this.lodgingId,
    this.establishment,
    this.imageUrl,
    this.nights,
    this.guests,
    this.unitPrice,
    this.paymentStatus,
    this.expiresAt,
    this.qr,
    this.checkoutUrl,
  });

  final int id;
  final String code;

  /// CREADA, CONFIRMADA, COMPLETADA, CANCELADA, EXPIRADA_LIBERADA o PAGO_PARCIAL.
  final String status;
  final String statusLabel;
  final String company;
  final int productId;
  final String productName;
  final String productType;
  final String city;
  final DateTime start;
  final DateTime end;
  final int quantity;
  final String unit;
  final String total;
  final String currencySymbol;
  final DateTime createdAt;
  final bool isLodging;
  final int? lodgingId;
  final String? establishment;
  final String? imageUrl;
  final int? nights;
  final int? guests;
  final String? unitPrice;
  final String? paymentStatus;
  final DateTime? expiresAt;

  /// Contenido firmado del QR. Solo en reservas pagadas.
  final String? qr;

  /// Solo en la respuesta de crear: la página de pago de Stripe.
  final String? checkoutUrl;

  bool get pendingPayment => status == 'CREADA';
  bool get confirmed => status == 'CONFIRMADA' || status == 'PAGO_PARCIAL';
  bool get finished => status == 'COMPLETADA';
  bool get inactive => status == 'CANCELADA' || status == 'EXPIRADA_LIBERADA';

  /// Título de la tarjeta: el hotel para una habitación, el producto si no.
  String get title => establishment ?? productName;

  String get totalLabel => '$currencySymbol $total';

  factory Booking.fromJson(Map<String, dynamic> json) {
    final product = json['producto'] as Map<String, dynamic>? ?? const {};
    final dates = json['fechas'] as Map<String, dynamic>? ?? const {};
    final amount = json['importe'] as Map<String, dynamic>? ?? const {};
    final payment = json['pago'] as Map<String, dynamic>?;
    DateTime day(Object? value) => DateTime.tryParse('${value ?? ''}') ?? DateTime(1970);
    return Booking(
      id: _int(json['id']) ?? 0,
      code: json['codigo']?.toString() ?? '',
      status: json['estado']?.toString() ?? '',
      statusLabel: json['estado_nombre']?.toString() ?? '',
      company: json['empresa']?.toString() ?? '',
      productId: _int(product['id']) ?? 0,
      productName: product['nombre']?.toString() ?? '',
      productType: product['tipo']?.toString() ?? '',
      city: [
        if (product['localidad'] != null) product['localidad'].toString(),
        product['ciudad']?.toString() ?? '',
      ].where((part) => part.isNotEmpty).join(', '),
      start: day(dates['inicio']),
      end: day(dates['fin']),
      nights: _int(dates['noches']),
      quantity: _int(amount['cantidad']) ?? 0,
      unit: amount['unidad']?.toString() ?? '',
      unitPrice: amount['precio_unitario']?.toString(),
      total: amount['total']?.toString() ?? '0.00',
      currencySymbol: json['moneda_simbolo']?.toString() ?? '',
      createdAt: DateTime.tryParse('${json['creado_en'] ?? ''}')?.toLocal() ?? DateTime(1970),
      isLodging: product['es_hospedaje'] == true,
      lodgingId: _int(product['hospedaje_id']),
      establishment: product['establecimiento']?.toString(),
      imageUrl: product['imagen_url']?.toString(),
      guests: _int(json['huespedes']),
      paymentStatus: payment?['estado']?.toString(),
      expiresAt: DateTime.tryParse('${json['vence_en'] ?? ''}')?.toLocal(),
      qr: json['qr']?.toString(),
      checkoutUrl: json['checkout_url']?.toString(),
    );
  }
}
