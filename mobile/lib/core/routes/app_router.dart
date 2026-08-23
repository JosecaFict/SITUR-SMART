import 'package:go_router/go_router.dart';

import '../../features/usuarios/presentation/pages/forgot_password_page.dart';
import '../../features/usuarios/presentation/pages/home_page.dart';
import '../../features/usuarios/presentation/pages/login_page.dart';
import '../../features/usuarios/presentation/pages/register_page.dart';

class AppRouter {
	AppRouter._();

	static final GoRouter router = GoRouter(
		initialLocation: '/login',
		routes: <RouteBase>[
			GoRoute(
				path: '/login',
				name: 'login',
				builder: (context, state) => const LoginPage(),
			),
			GoRoute(
				path: '/registrar-usuario',
				name: 'registrar-usuario',
				builder: (context, state) => const RegisterPage(),
			),
			GoRoute(
				path: '/recuperar-password',
				name: 'recuperar-password',
				builder: (context, state) => const ForgotPasswordPage(),
			),
			GoRoute(
				path: '/home',
				name: 'home',
				builder: (context, state) => const HomePage(),
			),
		],
	);
}
