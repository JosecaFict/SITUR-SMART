import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:mobile/core/routes/app_router.dart';
import 'package:mobile/core/storage/token_storage.dart';
import 'package:mobile/features/notificaciones/data/notifications_store.dart';
import 'package:mobile/features/notificaciones/data/push_service.dart';
import 'package:mobile/features/notificaciones/presentation/notification_bell.dart';
import 'package:mobile/features/notificaciones/presentation/notifications_page.dart';
import 'package:mobile/features/usuarios/presentation/pages/staff_web_panel_page.dart';

Map<String, dynamic> _json(
  int id, {
  bool leida = false,
  Map<String, dynamic>? datos,
}) => {
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
  Completer<void>? markReadResult;

  @override
  Future<NotificationsResult> list({int page = 1}) async =>
      NotificationsResult(items: items, hasNext: false);

  @override
  Future<int> unreadCount() async => unread;

  @override
  Future<void> markRead(int id) async {
    marked.add(id);
    await markReadResult?.future;
  }
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    PushService.onOpenRoute = null;
    PushService.instance.takePendingRoute();
  });

  tearDown(() {
    PushService.onOpenRoute = null;
    PushService.instance.takePendingRoute();
  });

  for (final type in ['INTERNA', 'OPERATIVA']) {
    test('lee metadatos de comunicación $type y los conserva al marcarla', () {
      final item = AppNotification.fromJson({
        ..._json(
          7,
          datos: {
            'comunicacion_id': '31',
            'remitente': 'Coordinación',
            'motivo': 'Cambio de horario',
            'tipo_comunicacion': type,
            'reserva_id': '12',
          },
        ),
        'tipo': 'COMUNICACION',
      }).copyWith(read: true);

      expect(item.isCommunication, isTrue);
      expect(item.communicationId, 31);
      expect(item.sender, 'Coordinación');
      expect(item.reason, 'Cambio de horario');
      expect(item.communicationType, type);
      expect(
        item.communicationTypeLabel,
        type == 'INTERNA' ? 'Interna' : 'Operativa',
      );
      expect(item.bookingId, 12);
      expect(item.read, isTrue);
    });
  }

  test('una comunicación admite datos opcionales ausentes o inválidos', () {
    final item = AppNotification.fromJson({
      ..._json(8, datos: {'comunicacion_id': 'inválido'}),
      'tipo': 'COMUNICACION',
    });
    expect(item.communicationId, isNull);
    expect(item.bookingId, isNull);
    expect(item.sender, isNull);
    expect(item.reason, isNull);
    expect(item.communicationTypeLabel, 'Comunicación');
  });

  test('lee un aviso y a qué reserva lleva', () {
    final item = AppNotification.fromJson(
      _json(1, datos: {'reserva_id': 12, 'codigo': 'RES-1'}),
    );
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
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          appBar: AppBar(actions: [NotificationBell(store: store)]),
        ),
      ),
    );
    expect(find.text('2'), findsOneWidget);
  });

  testWidgets('tocar un aviso sin leer lo marca y baja el contador', (
    tester,
  ) async {
    final service = _FakeService([
      AppNotification.fromJson(_json(1)),
      AppNotification.fromJson(_json(2, leida: true)),
    ]);
    final store = NotificationsStore(service: service);
    await store.refresh();

    await tester.pumpWidget(
      MaterialApp(
        home: NotificationsInboxPage(service: service, store: store),
      ),
    );
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
    expect(
      PushService.routeFor({'reserva_id': '12', 'tipo': 'RESERVA_CONFIRMADA'}),
      '/reserva/12',
    );
    expect(PushService.routeFor({'tipo': 'PAGO_REVISION'}), isNull);
    expect(PushService.routeFor({'reserva_id': 'x'}), isNull);
  });

  testWidgets(
    'si falla marcar leída conserva estado y contador, y permite reintentar',
    (tester) async {
      final service = _FakeService([AppNotification.fromJson(_json(1))]);
      final firstRequest = Completer<void>();
      service.markReadResult = firstRequest;
      final store = NotificationsStore(service: service);
      await tester.pumpWidget(
        MaterialApp(
          home: NotificationsInboxPage(service: service, store: store),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('¡Reserva confirmada!'));
      await tester.pump();
      expect(store.unread, 2, reason: 'no baja antes de la confirmación');
      expect(find.text('Marcar todas'), findsOneWidget);
      await tester.tap(find.text('¡Reserva confirmada!'));
      await tester.pump();
      expect(service.marked, [1], reason: 'no duplica peticiones pendientes');

      firstRequest.completeError(Exception('Sin red'));
      await tester.pumpAndSettle();
      expect(store.unread, 2);
      expect(find.text('Marcar todas'), findsOneWidget);
      expect(
        find.text('No se pudo marcar como leída. Vuelve a intentarlo.'),
        findsOneWidget,
      );

      service.markReadResult = null;
      await tester.tap(find.text('¡Reserva confirmada!'));
      await tester.pumpAndSettle();
      expect(service.marked, [1, 1]);
      expect(store.unread, 1);
      expect(find.text('Marcar todas'), findsNothing);
    },
  );

  test('los recordatorios también abren el detalle de la reserva', () {
    expect(
      PushService.routeFor({'reserva_id': '44', 'tipo': 'RECORDATORIO_24H'}),
      '/reserva/44',
    );
    expect(
      PushService.routeFor({'reserva_id': 45, 'tipo': 'RECORDATORIO_2H'}),
      '/reserva/45',
    );
  });

  test('el push de comunicación abre la bandeja, incluso con reserva', () {
    for (final data in [
      {'tipo': 'COMUNICACION', 'comunicacion_id': '31'},
      {'tipo': 'COMUNICACION', 'comunicacion_id': '31', 'reserva_id': '12'},
      {'tipo': 'COMUNICACION'},
    ]) {
      expect(PushService.routeFor(data), '/notificaciones');
    }
  });

  test(
    'un push espera el login y el destino se consume una sola vez',
    () async {
      final opened = <String>[];
      PushService.onOpenRoute = opened.add;
      await PushService.instance.openRoute('/notificaciones');
      expect(opened, isEmpty);
      expect(PushService.instance.takePendingRoute(), '/notificaciones');
      expect(PushService.instance.takePendingRoute(), isNull);

      await TokenStorage().saveTokens(access: 'access', refresh: 'refresh');
      await PushService.instance.openRoute('/notificaciones');
      expect(opened, ['/notificaciones']);
    },
  );

  test('cerrar sesión descarta el destino push pendiente', () async {
    await PushService.instance.openRoute('/notificaciones');
    await PushService.instance.unregisterDevice();
    expect(PushService.instance.takePendingRoute(), isNull);
  });

  testWidgets(
    'la comunicación muestra metadatos y permite leer todo sin abrir reserva',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final message =
          '${List.generate(100, (i) => 'Línea $i del comunicado.').join('\n')}\nFin del comunicado completo.';
      final service = _FakeService([
        AppNotification.fromJson({
          ..._json(
            9,
            datos: {
              'comunicacion_id': 31,
              'remitente': 'Coordinación',
              'motivo': 'Cambio de horario',
              'tipo_comunicacion': 'OPERATIVA',
              'reserva_id': 12,
            },
          ),
          'tipo': 'COMUNICACION',
          'titulo': 'Nuevo horario',
          'mensaje': message,
        }),
      ]);
      final store = NotificationsStore(service: service);
      await tester.pumpWidget(
        MaterialApp(
          home: NotificationsInboxPage(service: service, store: store),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Coordinación'), findsOneWidget);
      expect(find.text('Leer mensaje →'), findsOneWidget);
      await tester.tap(find.text('Nuevo horario'));
      await tester.pumpAndSettle();
      expect(find.text('Remitente: Coordinación'), findsOneWidget);
      expect(find.text('Motivo: Cambio de horario'), findsOneWidget);
      expect(find.text('Tipo: Operativa'), findsOneWidget);
      final body = tester.widget<SelectableText>(find.byType(SelectableText));
      expect(body.data, message);
      expect(body.maxLines, isNull);
      expect(service.marked, [9]);
      expect(store.unread, 1);
      final scroll = find.descendant(
        of: find.byType(BottomSheet),
        matching: find.byType(SingleChildScrollView),
      );
      await tester.drag(scroll, const Offset(0, -10000));
      await tester.pumpAndSettle();
      final scrollable = tester.state<ScrollableState>(
        find.descendant(of: scroll, matching: find.byType(Scrollable)).first,
      );
      expect(scrollable.position.extentAfter, closeTo(0, 0.01));
      expect(tester.takeException(), isNull);

      await tester.tap(find.byTooltip('Cerrar comunicación'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Nuevo horario'));
      await tester.pumpAndSettle();
      expect(service.marked, [9], reason: 'releer no vuelve a descontar');
      expect(store.unread, 1);
    },
  );

  testWidgets('el turista abre la reserva desde la comunicación completa', (
    tester,
  ) async {
    await _checkCommunicationBooking(tester, staff: false, bookingId: 12);
  });

  testWidgets('el personal lee la comunicación asociada sin botón de reserva', (
    tester,
  ) async {
    await _checkCommunicationBooking(tester, staff: true, bookingId: 12);
  });

  testWidgets('la comunicación sin reserva no muestra botón de reserva', (
    tester,
  ) async {
    await _checkCommunicationBooking(tester, staff: false);
  });

  testWidgets(
    'el personal abre la bandeja desde su campana y vuelve al panel',
    (tester) async {
      await TokenStorage().saveTokens(access: 'access', refresh: 'refresh');
      await TokenStorage().saveUser({
        'roles': ['TENANT_ADMIN'],
        'tenants': [
          {'id': 1},
        ],
      });
      final service = _FakeService(const []);
      final router = GoRouter(
        initialLocation: '/panel-web',
        redirect: (context, state) => AppRouter.redirectFor(state.uri),
        routes: [
          GoRoute(
            path: '/login',
            builder: (_, _) => const Scaffold(body: Text('Login')),
          ),
          GoRoute(
            path: '/panel-web',
            builder: (_, _) => const StaffWebPanelPage(),
          ),
          GoRoute(
            path: '/notificaciones',
            builder: (_, _) => NotificationsInboxPage(
              service: service,
              store: NotificationsStore(service: service),
            ),
          ),
        ],
      );
      addTearDown(router.dispose);
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      await tester.pumpAndSettle();
      expect(find.text('Ver comunicaciones y avisos'), findsOneWidget);
      expect(find.byType(NotificationBell), findsOneWidget);
      await tester.tap(find.byType(NotificationBell));
      await tester.pumpAndSettle();
      expect(find.byType(NotificationsInboxPage), findsOneWidget);
      router.pop();
      await tester.pumpAndSettle();
      expect(find.byType(StaffWebPanelPage), findsOneWidget);

      // Inicio de sesión después de tocar un push en frío.
      router.go('/login');
      await tester.pumpAndSettle();
      AppRouter.openHome(
        router,
        await TokenStorage().getUser(),
        pendingRoute: '/notificaciones',
      );
      await tester.pumpAndSettle();
      expect(find.byType(NotificationsInboxPage), findsOneWidget);
      router.pop();
      await tester.pumpAndSettle();
      expect(find.byType(StaffWebPanelPage), findsOneWidget);

      PushService.onOpenRoute = (route) => router.push(route);
      await PushService.instance.openRoute(
        PushService.routeFor({
          'tipo': 'COMUNICACION',
          'comunicacion_id': '31',
        })!,
      );
      await tester.pumpAndSettle();
      expect(find.byType(NotificationsInboxPage), findsOneWidget);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );

  test(
    'sin Firebase iniciado, registrar o quitar el celular no hace nada',
    () async {
      await PushService.instance.registerDevice();
      await PushService.instance.unregisterDevice();
      expect(PushService.instance.takePendingRoute(), isNull);
    },
  );
}

Future<void> _checkCommunicationBooking(
  WidgetTester tester, {
  required bool staff,
  int? bookingId,
}) async {
  await TokenStorage().saveTokens(access: 'access', refresh: 'refresh');
  await TokenStorage().saveUser({
    'roles': [staff ? 'SUPER_ADMIN' : 'CLIENTE'],
    'tenants': [],
  });
  final service = _FakeService([
    AppNotification.fromJson({
      ..._json(
        10,
        datos: {
          'comunicacion_id': 32,
          'remitente': 'Recepción',
          'motivo': 'Indicaciones',
          'tipo_comunicacion': 'OPERATIVA',
          'reserva_id': ?bookingId,
        },
      ),
      'tipo': 'COMUNICACION',
      'titulo': 'Indicaciones para tu llegada',
      'mensaje': 'Contenido completo de la comunicación asociada.',
    }),
  ]);
  final router = GoRouter(
    initialLocation: '/notificaciones',
    redirect: (context, state) => AppRouter.redirectFor(state.uri),
    routes: [
      GoRoute(
        path: '/notificaciones',
        builder: (_, _) => NotificationsInboxPage(
          service: service,
          store: NotificationsStore(service: service),
        ),
      ),
      GoRoute(
        path: '/reserva/:id',
        builder: (_, state) =>
            Scaffold(body: Text('Reserva ${state.pathParameters['id']}')),
      ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(MaterialApp.router(routerConfig: router));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Indicaciones para tu llegada'));
  await tester.pumpAndSettle();
  expect(
    tester.widget<SelectableText>(find.byType(SelectableText)).data,
    'Contenido completo de la comunicación asociada.',
  );
  if (!staff && bookingId != null) {
    expect(find.text('Ver reserva'), findsOneWidget);
    await tester.tap(find.text('Ver reserva'));
    await tester.pumpAndSettle();
    expect(find.text('Reserva 12'), findsOneWidget);
    expect(find.byType(BottomSheet), findsNothing);
  } else {
    expect(find.text('Ver reserva'), findsNothing);
  }
  expect(tester.takeException(), isNull);
  await tester.pumpWidget(const SizedBox.shrink());
}
