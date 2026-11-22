import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:mobile/core/routes/app_router.dart';
import 'package:mobile/core/storage/token_storage.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('la bandeja requiere sesión y el login sigue accesible', () async {
    expect(await AppRouter.redirectFor(Uri.parse('/notificaciones')), '/login');
    expect(await AppRouter.redirectFor(Uri.parse('/panel-web')), '/login');
    expect(await AppRouter.redirectFor(Uri.parse('/login')), isNull);
  });

  for (final user in [
    {
      'roles': ['TENANT_ADMIN'],
      'tenants': [
        {'id': 1},
      ],
    },
    {
      'roles': ['STAFF'],
      'tenants': [
        {'id': 2},
      ],
    },
    {
      'roles': ['SUPER_ADMIN'],
      'tenants': [],
    },
  ]) {
    test(
      'personal ${user['roles']} recibe avisos sin acceso a pantallas del turista',
      () async {
        await TokenStorage().saveTokens(access: 'access', refresh: 'refresh');
        await TokenStorage().saveUser(user);
        expect(
          await AppRouter.redirectFor(Uri.parse('/notificaciones')),
          isNull,
        );
        expect(await AppRouter.redirectFor(Uri.parse('/panel-web')), isNull);
        expect(
          await AppRouter.redirectFor(Uri.parse('/reserva/12')),
          '/panel-web',
        );
        expect(
          await AppRouter.redirectFor(Uri.parse('/explorar')),
          '/panel-web',
        );
        expect(await AppRouter.redirectFor(Uri.parse('/pagos')), '/panel-web');
      },
    );
  }

  test('el turista conserva su bandeja y el detalle de reservas', () async {
    await TokenStorage().saveTokens(access: 'access', refresh: 'refresh');
    await TokenStorage().saveUser({
      'roles': ['CLIENTE'],
      'tenants': [],
    });
    expect(await AppRouter.redirectFor(Uri.parse('/notificaciones')), isNull);
    expect(await AppRouter.redirectFor(Uri.parse('/reserva/12')), isNull);
    expect(await AppRouter.redirectFor(Uri.parse('/panel-web')), '/explorar');
  });

  test('cancelar openHome elimina ambos listeners y es idempotente', () {
    final router = _navigationRouter();
    addTearDown(router.dispose);
    final cancel = AppRouter.openHome(router, {
      'roles': ['SUPER_ADMIN'],
    }, pendingRoute: '/notificaciones');
    expect(_hasListeners(router.routerDelegate), isTrue);
    expect(_hasListeners(router.routeInformationProvider), isTrue);
    cancel();
    cancel();
    expect(_hasListeners(router.routerDelegate), isFalse);
    expect(_hasListeners(router.routeInformationProvider), isFalse);
  });

  test('otra navegación cancela openHome antes de completar el inicio', () {
    final router = _navigationRouter();
    addTearDown(router.dispose);
    AppRouter.openHome(router, {
      'roles': ['SUPER_ADMIN'],
    }, pendingRoute: '/notificaciones');
    router.go('/login');
    expect(_hasListeners(router.routerDelegate), isFalse);
    expect(_hasListeners(router.routeInformationProvider), isFalse);
  });

  testWidgets(
    'desmontar el origen limpia listeners aunque el guard siga pendiente',
    (tester) async {
      final gate = Completer<String?>();
      final router = _navigationRouter(
        redirect: (_, state) =>
            state.uri.path == '/panel-web' ? gate.future : null,
      );
      addTearDown(router.dispose);
      VoidCallback? cancel;
      await tester.pumpWidget(
        _CancelOnDispose(
          onDispose: () => cancel?.call(),
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pumpAndSettle();
      cancel = AppRouter.openHome(router, {
        'roles': ['SUPER_ADMIN'],
      }, pendingRoute: '/notificaciones');
      await tester.pump();
      await tester.pumpWidget(const SizedBox.shrink());
      expect(_hasListeners(router.routerDelegate), isFalse);
      expect(_hasListeners(router.routeInformationProvider), isFalse);
      gate.complete(null);
      await tester.pump();
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('un guard que conserva el login no deja listeners indefinidos', (
    tester,
  ) async {
    final router = _navigationRouter(
      redirect: (_, state) => state.uri.path == '/panel-web' ? '/login' : null,
    );
    addTearDown(router.dispose);
    await tester.pumpWidget(MaterialApp.router(routerConfig: router));
    await tester.pumpAndSettle();
    AppRouter.openHome(router, {
      'roles': ['SUPER_ADMIN'],
    }, pendingRoute: '/notificaciones');
    await tester.pumpAndSettle();
    expect(find.text('/login'), findsOneWidget);
    expect(find.text('/notificaciones'), findsNothing);
    await tester.pump(const Duration(seconds: 30));
    await tester.pumpWidget(const SizedBox.shrink());
    expect(_hasListeners(router.routerDelegate), isFalse);
    expect(_hasListeners(router.routeInformationProvider), isFalse);
  });
}

bool _hasListeners(ChangeNotifier notifier) {
  // Solo en pruebas: comprueba que los listeners se liberan realmente.
  // ignore: invalid_use_of_protected_member
  return notifier.hasListeners;
}

GoRouter _navigationRouter({GoRouterRedirect? redirect}) => GoRouter(
  initialLocation: '/login',
  redirect: redirect,
  routes: [
    for (final path in ['/login', '/panel-web', '/notificaciones'])
      GoRoute(
        path: path,
        builder: (_, _) => Scaffold(body: Text(path)),
      ),
  ],
);

class _CancelOnDispose extends StatefulWidget {
  const _CancelOnDispose({required this.onDispose, required this.child});

  final VoidCallback onDispose;
  final Widget child;

  @override
  State<_CancelOnDispose> createState() => _CancelOnDisposeState();
}

class _CancelOnDisposeState extends State<_CancelOnDispose> {
  @override
  void dispose() {
    widget.onDispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
