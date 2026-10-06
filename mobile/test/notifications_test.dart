import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:mobile/features/notificaciones/data/notifications_store.dart';
import 'package:mobile/features/notificaciones/data/push_service.dart';
import 'package:mobile/features/notificaciones/presentation/notification_bell.dart';
import 'package:mobile/features/notificaciones/presentation/notifications_page.dart';

Map<String, dynamic> _json(int id, {bool leida = false, Map<String, dynamic>? datos}) => {
      'id': id,
      'tipo': 'RESERVA_CONFIRMADA',
      'titulo': '¡Reserva confirmada!',
      'mensaje': 'Hotel Los Tajibos · 20 oct 2026. Tu código es RES-1.',
      'datos': datos ?? {},
      'leida': leida,
      'creado_en': '2026-10-06T14:55:00-04:00',
    };

class _FakeService extends NotificationsService {
  _FakeService(this.items);

  final List<AppNotification> items;
  final List<int> marked = [];
  int unread = 2;

  @override
  Future<NotificationsResult> list({int page = 1}) async => NotificationsResult(items: items, hasNext: false);

  @override
  Future<int> unreadCount() async => unread;

  @override
  Future<void> markRead(int id) async => marked.add(id);
}

void main() {
  test('lee un aviso y a qué reserva lleva', () {
    final item = AppNotification.fromJson(_json(1, datos: {'reserva_id': 12, 'codigo': 'RES-1'}));
    expect(item.bookingId, 12);
    expect(item.read, isFalse);
    expect(AppNotification.fromJson(_json(2)).bookingId, isNull);
  });

  test('el contador baja al leer y vuelve a cero al limpiar', () async {
    final store = NotificationsStore(service: _FakeService(const []));
    await store.refresh();
    expect(store.unread, 2);
    store.decrement();
    expect(store.unread, 1);
    store.clear();
    expect(store.unread, 0);
    store.decrement();
    expect(store.unread, 0, reason: 'nunca negativo');
  });

  testWidgets('la campana muestra cuántos avisos faltan leer', (tester) async {
    final store = NotificationsStore(service: _FakeService(const []));
    await store.refresh();
    await tester.pumpWidget(MaterialApp(home: Scaffold(appBar: AppBar(actions: [NotificationBell(store: store)]))));
    expect(find.text('2'), findsOneWidget);
  });

  testWidgets('tocar un aviso sin leer lo marca y baja el contador', (tester) async {
    final service = _FakeService([
      AppNotification.fromJson(_json(1)),
      AppNotification.fromJson(_json(2, leida: true)),
    ]);
    final store = NotificationsStore(service: service);
    await store.refresh();

    await tester.pumpWidget(MaterialApp(home: NotificationsInboxPage(service: service, store: store)));
    await tester.pumpAndSettle();
    expect(find.text('Marcar todas'), findsOneWidget);

    await tester.tap(find.text('¡Reserva confirmada!').first);
    await tester.pump();

    expect(service.marked, [1]);
    expect(store.unread, 1);
    expect(find.text('Marcar todas'), findsNothing);
  });

  test('un push con reserva abre esa reserva; sin reserva no navega', () {
    // FCM entrega los datos como texto.
    expect(PushService.routeFor({'reserva_id': '12', 'tipo': 'RESERVA_CONFIRMADA'}), '/reserva/12');
    expect(PushService.routeFor({'tipo': 'PAGO_REVISION'}), isNull);
    expect(PushService.routeFor({'reserva_id': 'x'}), isNull);
  });

  test('sin Firebase iniciado, registrar o quitar el celular no hace nada', () async {
    await PushService.instance.registerDevice();
    await PushService.instance.unregisterDevice();
    expect(PushService.instance.takePendingRoute(), isNull);
  });
}
