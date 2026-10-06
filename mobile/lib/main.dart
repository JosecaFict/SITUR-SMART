import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'core/network/api_client.dart';
import 'core/routes/app_router.dart';
import 'core/theme/app_theme.dart';
import 'features/notificaciones/data/push_service.dart';

/// Para avisar de un push que llega con la app abierta desde cualquier pantalla.
final GlobalKey<ScaffoldMessengerState> scaffoldMessengerKey = GlobalKey<ScaffoldMessengerState>();

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Fechas en español ("sáb 10 oct 2026") en reservas y voucher.
  await initializeDateFormatting('es');
  // Si la sesión vence y no puede renovarse, se vuelve al login desde
  // cualquier pantalla.
  ApiClient.onSessionExpired = () => AppRouter.router.go('/login');

  PushService.onOpenRoute = (route) => AppRouter.router.push(route);
  PushService.onForegroundMessage = _showForegroundPush;
  await PushService.instance.init();

  runApp(const ProviderScope(child: SiturSmartApp()));
}

void _showForegroundPush(String title, String body, String? route) {
  scaffoldMessengerKey.currentState
    ?..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 6),
        content: Text(body.isEmpty ? title : '$title\n$body'),
        action: route == null
            ? null
            : SnackBarAction(label: 'Ver', onPressed: () => AppRouter.router.push(route)),
      ),
    );
}

class SiturSmartApp extends StatelessWidget {
  const SiturSmartApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      debugShowCheckedModeBanner: false,
      title: 'SITUR-SMART',
      theme: AppTheme.light,
      scaffoldMessengerKey: scaffoldMessengerKey,
      routerConfig: AppRouter.router,
    );
  }
}
