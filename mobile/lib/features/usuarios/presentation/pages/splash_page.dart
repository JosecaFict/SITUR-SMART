import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
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
    context.go(user == null ? '/login' : AuthService.homeRouteFor(user));
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: AppTheme.accentDark,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.travel_explore, color: Colors.white, size: 56),
            SizedBox(height: 16),
            Text(
              'SITUR-SMART',
              style: TextStyle(color: Colors.white, fontSize: 26, fontWeight: FontWeight.bold),
            ),
            SizedBox(height: 24),
            CircularProgressIndicator(color: Colors.white),
          ],
        ),
      ),
    );
  }
}
