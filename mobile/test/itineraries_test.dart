import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'package:mobile/features/itinerarios/data/itinerary_models.dart';
import 'package:mobile/features/itinerarios/data/itinerary_service.dart';
import 'package:mobile/features/itinerarios/presentation/itineraries_view.dart';
import 'package:mobile/features/itinerarios/presentation/itinerary_detail_page.dart';

Map<String, dynamic> _detailJson() => {
      'id': 3,
      'nombre': 'Viaje a Santa Cruz',
      'ciudad_id': 7,
      'ciudad': 'Santa Cruz de la Sierra',
      'inicio': '2026-10-10',
      'fin': '2026-10-12',
      'notas': 'Llevar repelente',
      'dias': 3,
      'actividades': 2,
      'agenda': [
        {
          'fecha': '2026-10-10',
          'reservas': [
            {
              'tipo': 'RESERVA',
              'reserva_id': 41,
              'codigo': 'RES-AB12',
              'momento': 'LLEGADA',
              'titulo': 'Los Tajibos',
              'producto': {'id': 90, 'hospedaje_id': 5, 'imagen_url': null, 'es_hospedaje': true},
              'fechas': {'inicio': '2026-10-10', 'fin': '2026-10-12', 'noches': 2},
            },
          ],
          'actividades': [
            {
              'id': 1,
              'tipo': 'PRODUCTO',
              'fecha': '2026-10-10',
              'hora': '19:00',
              'titulo': 'Cena en Jardín de Asia',
              'nota': null,
              'producto': {'id': 12, 'tipo_codigo': 'RESTAURANTE', 'nombre': 'Jardín de Asia', 'moneda_simbolo': 'Bs'},
            },
          ],
        },
        {'fecha': '2026-10-11', 'reservas': [], 'actividades': []},
        {
          'fecha': '2026-10-12',
          'reservas': [],
          'actividades': [
            {
              'id': 2,
              'tipo': 'LIBRE',
              'fecha': '2026-10-12',
              'hora': null,
              'titulo': 'Comprar recuerdos',
              'nota': 'Mercado Los Pozos',
              'producto': null,
            },
          ],
        },
      ],
    };

class _FakeService extends ItineraryService {
  @override
  Future<List<ItinerarySummary>> list() async => const [];

  @override
  Future<ItineraryDetail> detail(int id) async => ItineraryDetail.fromJson(_detailJson());
}

void main() {
  setUpAll(() => initializeDateFormatting('es'));

  test('la agenda mezcla reservas y actividades y sabe a dónde llevar', () {
    final detail = ItineraryDetail.fromJson(_detailJson());

    expect(detail.summary.days, 3);
    expect(detail.agenda.map((d) => d.date.day), [10, 11, 12]);
    expect(detail.agenda[1].isEmpty, isTrue);

    final [booking, dinner] = detail.agenda[0].items;
    expect(booking.isBooking, isTrue);
    expect(booking.moment, 'LLEGADA');
    expect(booking.route, '/reserva/41');
    expect(dinner.time, '19:00');
    expect(dinner.route, '/producto/12');

    final free = detail.agenda[2].items.single;
    expect(free.kind, 'LIBRE');
    expect(free.route, isNull);
    expect(free.note, 'Mercado Los Pozos');
  });

  test('un producto que es un hotel lleva a su hospedaje', () {
    final item = AgendaItem.activity({
      'id': 9,
      'tipo': 'PRODUCTO',
      'titulo': 'Los Tajibos',
      'producto': {'id': 90, 'tipo_codigo': 'HOTEL', 'nombre': 'Los Tajibos', 'hospedaje_id': 5},
    });
    expect(item.route, '/hospedaje/5');
  });

  test('fechas del viaje en una línea', () {
    expect(itineraryDates(DateTime(2026, 10, 6), DateTime(2026, 10, 9)), '6 – 9 oct 2026');
    expect(itineraryDates(DateTime(2026, 9, 28), DateTime(2026, 10, 2)), '28 sept – 2 oct 2026');
    expect(apiDate(DateTime(2026, 1, 5)), '2026-01-05');
  });

  testWidgets('el detalle muestra cada día con sus reservas y actividades', (tester) async {
    await tester.pumpWidget(MaterialApp(home: ItineraryDetailPage(itineraryId: 3, service: _FakeService())));
    await tester.pumpAndSettle();

    expect(find.text('Viaje a Santa Cruz'), findsOneWidget);
    expect(find.text('Sábado 10 oct'), findsOneWidget);
    expect(find.text('Los Tajibos'), findsOneWidget);
    expect(find.text('Llegada · RES-AB12 · Pagada'), findsOneWidget);
    expect(find.text('19:00'), findsOneWidget);
    expect(find.text('Día libre'), findsOneWidget);
    expect(find.text('Agregar'), findsNWidgets(3));
  });

  testWidgets('sin itinerarios invita a crear el primero', (tester) async {
    await tester.pumpWidget(MaterialApp(home: ItinerariesView(service: _FakeService())));
    await tester.pumpAndSettle();

    expect(find.text('Arma tu primer itinerario'), findsOneWidget);
    expect(find.text('Nuevo'), findsOneWidget);
  });
}
