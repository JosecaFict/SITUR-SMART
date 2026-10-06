import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../features/usuarios/data/auth_service.dart';
import '../../features/usuarios/presentation/pages/forgot_password_page.dart';
import '../../features/usuarios/presentation/pages/login_page.dart';
import '../../features/usuarios/presentation/pages/register_page.dart';
import '../../features/usuarios/presentation/pages/splash_page.dart';
import '../../features/usuarios/presentation/pages/users_page.dart';

import '../../features/main/presentation/main_shell_page.dart';



class AppRouter {

  AppRouter._();



  static final GoRouter router = GoRouter(

    initialLocation: '/',


    routes: <RouteBase>[
      GoRoute(
        path: '/',
        name: 'inicio',
        builder: (context, state) => const SplashPage(),
      ),



      GoRoute(

        path: '/login',

        name: 'login',

        builder: (context, state) =>
            const LoginPage(),

      ),




      GoRoute(

        path: '/registrar-usuario',

        name: 'registrar-usuario',

        builder: (context, state) =>
            const RegisterPage(),

      ),




      GoRoute(

        path: '/recuperar-password',

        name: 'recuperar-password',

        builder: (context, state) =>
            const ForgotPasswordPage(),

      ),





      GoRoute(

        path: '/dashboard',

        name: 'dashboard',

        builder: (context, state) =>
            const MainShellPage(),

      ),





      GoRoute(

        path: '/users',

        name: 'users',

        builder: (context, state) =>
            const UsersPage(),

      ),





      // Menú Drawer
      // Pendientes de módulos completos



      GoRoute(

        path: '/explorar',

        name: 'explorar',

        builder: (context, state) =>
            const _PlaceholderPage(
              titulo: 'Explorar',
            ),

      ),





      GoRoute(

        path: '/perfil',

        name: 'perfil',

        builder: (context, state) =>
            const _PlaceholderPage(
              titulo: 'Mi Perfil',
            ),

      ),





      GoRoute(

        path: '/empresas',

        name: 'empresas',

        builder: (context, state) =>
            const _PlaceholderPage(
              titulo: 'Empresas',
            ),

      ),





      GoRoute(

        path: '/roles',

        name: 'roles',

        builder: (context, state) =>
            const MainShellPage(),

      ),





      GoRoute(

        path: '/catalogo',

        name: 'catalogo',

        builder: (context, state) =>
            const _PlaceholderPage(
              titulo: 'Catálogo',
            ),

      ),





      GoRoute(

        path: '/bitacora',

        name: 'bitacora',

        builder: (context, state) =>
            const MainShellPage(),

      ),



    ],


  );


}





/// Pantalla provisoria de un módulo que todavía no está construido. Explica qué
/// falta y permite cerrar sesión, para que nadie quede atrapado en ella.
class _PlaceholderPage extends StatelessWidget {
  final String titulo;

  const _PlaceholderPage({
    required this.titulo,
  });

  Future<void> _logout(BuildContext context) async {
    final router = GoRouter.of(context);
    await AuthService().logout();
    router.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(titulo),
        actions: [
          IconButton(
            tooltip: 'Cerrar sesión',
            icon: const Icon(Icons.logout),
            onPressed: () => _logout(context),
          ),
        ],
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.construction_outlined, size: 56, color: Colors.grey),
              const SizedBox(height: 16),
              Text(
                titulo,
                style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              const Text(
                'Este módulo todavía está en construcción.',
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
