import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../features/usuarios/presentation/pages/forgot_password_page.dart';
import '../../features/usuarios/presentation/pages/login_page.dart';
import '../../features/usuarios/presentation/pages/register_page.dart';
import '../../features/usuarios/presentation/pages/users_page.dart';

import '../../features/main/presentation/main_shell_page.dart';



class AppRouter {

  AppRouter._();



  static final GoRouter router = GoRouter(

    initialLocation: '/login',


    routes: <RouteBase>[



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





class _PlaceholderPage extends StatelessWidget {


  final String titulo;



  const _PlaceholderPage({

    required this.titulo,

  });



  @override
  Widget build(BuildContext context) {


    return Scaffold(

      appBar: AppBar(

        title:
            Text(titulo),

      ),


      body:
          Center(

        child:
            Text(

          titulo,

          style:
              const TextStyle(

            fontSize: 24,

            fontWeight:
                FontWeight.bold,

          ),

        ),

      ),

    );


  }

}