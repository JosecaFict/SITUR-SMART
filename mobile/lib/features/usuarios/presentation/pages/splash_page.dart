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
      context.go('/login');
      return;
    }
    context.go(AuthService.homeRouteFor(user));
    // La app se abrió tocando un push: se abre esa reserva sobre el inicio.
    final pushRoute = PushService.instance.takePendingRoute();
    if (pushRoute != null) AppRouter.router.push(pushRoute);
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
