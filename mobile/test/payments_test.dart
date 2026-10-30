import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:mobile/features/pagos/data/payment_models.dart';
import 'package:mobile/features/pagos/data/payment_service.dart';
import 'package:mobile/features/pagos/presentation/my_payments_page.dart';

class _FakePaymentService extends PaymentService {
  _FakePaymentService(this.items);
  final List<PaymentMovement> items;

  @override
  Future<List<PaymentMovement>> mine() async => items;
}

void main() {
  test('lee un pago con su reembolso', () {
    final payment = PaymentMovement.fromJson({
      'id': 3, 'reserva_id': 9, 'reserva': 'RES-ABC', 'empresa': 'ToursBo',
      'producto': {'nombre': 'Tour por Sucre'}, 'simbolo': 'Bs', 'amount': '200.00',
      'method': 'TARJETA', 'status': 'APROBADO', 'created_at': '2026-10-30T10:00:00-04:00',
      'reembolsos': [{'id': 2, 'estado': 'COMPLETADO', 'monto': '150.00', 'solicitado_en': '2026-10-30T11:00:00-04:00'}],
    });
    expect(payment.bookingCode, 'RES-ABC');
    expect(payment.refunds.single.amount, '150.00');
  });

  testWidgets('Mis pagos muestra cobro y devolución', (tester) async {
    final payment = PaymentMovement.fromJson({
      'id': 3, 'reserva_id': 9, 'reserva': 'RES-ABC', 'empresa': 'ToursBo',
      'producto': {'nombre': 'Tour por Sucre'}, 'simbolo': 'Bs', 'amount': '200.00',
      'method': 'TARJETA', 'status': 'APROBADO', 'created_at': '2026-10-30T10:00:00-04:00',
      'reembolsos': [{'id': 2, 'estado': 'COMPLETADO', 'monto': '150.00', 'solicitado_en': '2026-10-30T11:00:00-04:00'}],
    });
    await tester.pumpWidget(MaterialApp(home: MyPaymentsPage(service: _FakePaymentService([payment]))));
    await tester.pumpAndSettle();
    expect(find.text('Tour por Sucre'), findsOneWidget);
    expect(find.text('Bs 200.00'), findsOneWidget);
    expect(find.textContaining('Bs 150.00'), findsOneWidget);
  });
}
