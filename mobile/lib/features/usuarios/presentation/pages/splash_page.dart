import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/routes/app_router.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../notificaciones/data/push_service.dart';
import '../../data/auth_service.dart';

/// Primera pantalla de la app. Si hay una sesión guardada la renueva y entra
/// directo; si no, va al login. Así no hay que iniciar sesión cada vez que se
/// abre la app.
class SplashPage extends StatefulWidget {
  const SplashPage({super.key});

  @override
  State<SplashPage> createState() => _SplashPageState();
}

class _SplashPageState extends State<SplashPage> {
  VoidCallback? _cancelHomeNavigation;

  @override
  void dispose() {
    _cancelHomeNavigation?.call();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    _start();
  }

  Future<void> _start() async {
    Map<String, dynamic>? user;
    try {
      user = await AuthService().restoreSession();
    } catch (_) {
      user = null;
    }
    if (!mounted) return;
    if (user == null) {
      // Una oferta tocada sin sesión se abre igual, encima del login.
      final offer = PushService.instance.takePublicPendingRoute();
      if (offer == null) {
        context.go('/login');
        return;
      }
      _cancelHomeNavigation = AppRouter.openHome(
        GoRouter.of(context),
        null,
        pendingRoute: offer,
        homeRoute: '/login',
      );
      return;
    }
    _cancelHomeNavigation = AppRouter.openHome(
      GoRouter.of(context),
      user,
      pendingRoute: PushService.instance.takePendingRoute(),
    );
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: AppTheme.accentDark,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Versión con "SITUR" blanco, sobre el verde del splash.
            Padding(
              padding: EdgeInsets.symmetric(horizontal: 48),
              child: Image(image: AssetImage('assets/branding/logo-oscuro.png'), semanticLabel: 'SITUR-SMART'),
            ),
            SizedBox(height: 32),
            CircularProgressIndicator(color: Colors.white),
          ],
        ),
      ),
    );
  }
}
