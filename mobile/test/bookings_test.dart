import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'package:mobile/features/reservas/data/booking_models.dart';
import 'package:mobile/features/reservas/data/booking_service.dart';
import 'package:mobile/features/reservas/presentation/booking_detail_page.dart';
import 'package:mobile/features/reservas/presentation/my_trips_page.dart';

/// Forma exacta que devuelve GET me/reservas/{id}/ (BookingSerializer).
Map<String, dynamic> _json({
  int id = 5,
  String estado = 'CONFIRMADA',
  String nombre = 'Confirmada',
  String? qr = 'token-firmado',
  String inicio = '2026-10-20',
}) =>
    {
      'id': id,
      'codigo': 'RES-1A2B3C4D',
      'orden': 'ORD-9F8E7D6C',
      'estado': estado,
      'estado_nombre': nombre,
      'empresa': 'Los Tajibos',
      'producto': {
        'id': 40,
        'nombre': 'Suite Ejecutiva',
        'tipo_codigo': 'HABITACION',
        'tipo': 'Habitacion',
        'ciudad': 'Santa Cruz de la Sierra',
        'localidad': 'Equipetrol',
        'imagen_url': null,
        'es_hospedaje': true,
        'hospedaje_id': 3,
        'establecimiento': 'Hotel Los Tajibos',
      },
      'fechas': {'inicio': inicio, 'fin': '2026-10-22', 'noches': 2},
      'importe': {'cantidad': 1, 'unidad': 'habitación', 'precio_unitario': '850.00', 'total': '1700.00'},
      'huespedes': 2,
      'moneda_codigo': 'BOB',
      'moneda_simbolo': 'Bs',
      'pago': {'estado': 'APROBADO', 'metodo': 'TARJETA', 'proveedor': 'STRIPE', 'monto': '1700.00'},
      'vence_en': estado == 'CREADA' ? '2026-10-06T15:30:00-04:00' : null,
      'qr': qr,
      'creado_en': '2026-10-06T14:55:00-04:00',
    };

class _FakeBookingService extends BookingService {
  _FakeBookingService(this.bookings);

  final List<Booking> bookings;

  @override
  Future<List<Booking>> list() async => bookings;

  @override
  Future<Booking> detail(int id) async => bookings.firstWhere((booking) => booking.id == id);
}

void main() {
  setUpAll(() => initializeDateFormatting('es'));

  test('lee una reserva tal como la devuelve el backend', () {
    final booking = Booking.fromJson(_json());
    expect(booking.title, 'Hotel Los Tajibos');
    expect(booking.city, 'Equipetrol, Santa Cruz de la Sierra');
    expect(booking.nights, 2);
    expect(booking.totalLabel, 'Bs 1700.00');
    expect(booking.confirmed, isTrue);
    expect(booking.lodgingId, 3);
    expect(booking.start, DateTime(2026, 10, 20));
  });

  test('el pedido solo manda la salida y los huéspedes en una habitación', () {
    final room = BookingRequest(
      productId: 40,
      start: DateTime(2026, 10, 20),
      end: DateTime(2026, 10, 22),
      quantity: 1,
      guests: 2,
    );
    expect(room.toJson(), {
      'producto_id': 40,
      'fecha_inicio': '2026-10-20',
      'fecha_fin': '2026-10-22',
      'cantidad': 1,
      'huespedes': 2,
    });
    final tour = BookingRequest(productId: 7, start: DateTime(2026, 1, 5), quantity: 3);
    expect(tour.toJson(), {'producto_id': 7, 'fecha_inicio': '2026-01-05', 'cantidad': 3});
  });

  testWidgets('Mis viajes separa pendientes, próximos y anteriores', (tester) async {
    final service = _FakeBookingService([
      Booking.fromJson(_json(id: 1, estado: 'CREADA', nombre: 'Pendiente de pago', qr: null)),
      Booking.fromJson(_json(id: 2)),
      Booking.fromJson(_json(id: 3, estado: 'CANCELADA', nombre: 'Cancelada', qr: null)),
    ]);
    await tester.pumpWidget(MaterialApp(home: MyTripsPage(service: service)));
    await tester.pumpAndSettle();

    expect(find.text('Pendientes de pago'), findsOneWidget);
    expect(find.text('Próximos'), findsOneWidget);
    expect(find.text('Anteriores'), findsOneWidget);
  });

  testWidgets('una reserva pagada muestra su voucher', (tester) async {
    final service = _FakeBookingService([Booking.fromJson(_json())]);
    await tester.pumpWidget(MaterialApp(home: BookingDetailPage(bookingId: 5, service: service)));
    await tester.pumpAndSettle();

    expect(find.text('Tu voucher'), findsOneWidget);
    expect(find.text('Pagar ahora'), findsNothing);
    expect(find.text('Total pagado'), findsOneWidget);
  });

  testWidgets('una reserva pendiente ofrece pagar o cancelar', (tester) async {
    final service = _FakeBookingService([
      Booking.fromJson(_json(estado: 'CREADA', nombre: 'Pendiente de pago', qr: null)),
    ]);
    await tester.pumpWidget(MaterialApp(home: BookingDetailPage(bookingId: 5, service: service)));
    await tester.pump();
    await tester.pump();

    expect(find.text('Pagar ahora'), findsOneWidget);
    expect(find.text('Cancelar reserva'), findsOneWidget);
    expect(find.text('Tu voucher'), findsNothing);

    // La pantalla consulta sola cada pocos segundos mientras espera el pago:
    // se desmonta para que el temporizador no quede vivo al terminar.
    await tester.pumpWidget(const SizedBox());
  });
}
