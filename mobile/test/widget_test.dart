import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:mobile/features/usuarios/data/auth_service.dart';
import 'package:mobile/features/usuarios/presentation/pages/staff_web_panel_page.dart';
import 'package:mobile/main.dart';

void main() {
  testWidgets('Sin sesión guardada, la app abre el login con sus enlaces', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(const ProviderScope(child: SiturSmartApp()));
    await tester.pumpAndSettle();

    expect(find.text('Bienvenido de vuelta'), findsOneWidget);
    expect(find.text('Iniciar sesión'), findsOneWidget);
    expect(find.text('¿Olvidaste tu contraseña?'), findsOneWidget);
    expect(find.text('Crear cuenta'), findsOneWidget);
  });

  group('AuthService.homeRouteFor', () {
    test('un turista va a Explorar', () {
      expect(
        AuthService.homeRouteFor({'roles': ['CLIENTE'], 'tenants': []}),
        '/explorar',
      );
    });

    test('el personal de una empresa va al aviso del panel web', () {
      expect(
        AuthService.homeRouteFor({
          'roles': ['TENANT_ADMIN'],
          'tenants': [
            {'id': 1, 'name': 'Hotel Cortez'},
          ],
        }),
        '/panel-web',
      );
    });

    test('el SuperAdmin va al aviso del panel web', () {
      expect(
        AuthService.homeRouteFor({'roles': ['SUPER_ADMIN'], 'tenants': []}),
        '/panel-web',
      );
    });

    test('sin datos de usuario va a Explorar', () {
      expect(AuthService.homeRouteFor(null), '/explorar');
    });
  });

  testWidgets('el personal ve que la administración está en el panel web', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: StaffWebPanelPage()));

    expect(find.text('La administración se hace desde el panel web'), findsOneWidget);
    expect(find.text('Abrir el panel web'), findsOneWidget);
    expect(find.text('Cerrar sesión'), findsOneWidget);
  });
}
