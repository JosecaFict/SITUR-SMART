import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'core/network/api_client.dart';
import 'core/routes/app_router.dart';
import 'core/theme/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Fechas en español ("sáb 10 oct 2026") en reservas y voucher.
  await initializeDateFormatting('es');
  // Si la sesión vence y no puede renovarse, se vuelve al login desde
  // cualquier pantalla.
  ApiClient.onSessionExpired = () => AppRouter.router.go('/login');
  runApp(const ProviderScope(child: SiturSmartApp()));
}

class SiturSmartApp extends StatelessWidget {
  const SiturSmartApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      debugShowCheckedModeBanner: false,
      title: 'SITUR-SMART',
      theme: AppTheme.light,
      routerConfig: AppRouter.router,
    );
  }
}
