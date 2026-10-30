int _int(Object? value) => value is int ? value : int.tryParse('${value ?? ''}') ?? 0;

class RefundMovement {
  const RefundMovement({required this.id, required this.status, required this.amount, required this.requestedAt});
  final int id;
  final String status;
  final String amount;
  final DateTime requestedAt;

  factory RefundMovement.fromJson(Map<String, dynamic> json) => RefundMovement(
        id: _int(json['id']),
        status: json['estado']?.toString() ?? '',
        amount: json['monto']?.toString() ?? '0.00',
        requestedAt: DateTime.tryParse('${json['procesado_en'] ?? json['solicitado_en'] ?? ''}')?.toLocal() ?? DateTime(1970),
      );
}

class PaymentMovement {
  const PaymentMovement({required this.id, required this.bookingId, required this.bookingCode, required this.company, required this.product, required this.currencySymbol, required this.amount, required this.method, required this.status, required this.createdAt, required this.refunds});
  final int id;
  final int bookingId;
  final String bookingCode;
  final String company;
  final String product;
  final String currencySymbol;
  final String amount;
  final String method;
  final String status;
  final DateTime createdAt;
  final List<RefundMovement> refunds;

  factory PaymentMovement.fromJson(Map<String, dynamic> json) {
    final product = json['producto'] as Map<String, dynamic>?;
    return PaymentMovement(
      id: _int(json['id']), bookingId: _int(json['reserva_id']), bookingCode: json['reserva']?.toString() ?? '',
      company: json['empresa']?.toString() ?? '', product: product?['nombre']?.toString() ?? 'Reserva turística',
      currencySymbol: json['simbolo']?.toString() ?? '', amount: json['amount']?.toString() ?? '0.00',
      method: json['method']?.toString() ?? '', status: json['status']?.toString() ?? '',
      createdAt: DateTime.tryParse('${json['processed_at'] ?? json['created_at'] ?? ''}')?.toLocal() ?? DateTime(1970),
      refunds: (json['reembolsos'] as List<dynamic>? ?? const []).whereType<Map<String, dynamic>>().map(RefundMovement.fromJson).toList(),
    );
  }
}
