import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/routes/app_router.dart';
import 'core/theme/app_theme.dart';

void main() {
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
