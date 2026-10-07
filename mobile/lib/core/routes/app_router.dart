import 'package:go_router/go_router.dart';

import '../../features/asistente/presentation/assistant_page.dart';
import '../../features/favoritos/presentation/favorites_page.dart';
import '../../features/itinerarios/presentation/itinerary_detail_page.dart';
import '../../features/marketplace/presentation/explore_page.dart';
import '../../features/marketplace/presentation/lodging_detail_page.dart';
import '../../features/marketplace/presentation/product_detail_page.dart';
import '../../features/notificaciones/presentation/notifications_page.dart';
import '../../features/perfil/presentation/profile_page.dart';
import '../../features/reservas/presentation/booking_detail_page.dart';
import '../../features/reservas/presentation/my_trips_page.dart';
import '../../features/turista/tourist_shell_page.dart';
import '../../features/usuarios/presentation/pages/forgot_password_page.dart';
import '../../features/usuarios/presentation/pages/login_page.dart';
import '../../features/usuarios/presentation/pages/register_page.dart';
import '../../features/usuarios/presentation/pages/splash_page.dart';
import '../../features/usuarios/presentation/pages/staff_web_panel_page.dart';

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

      // App del turista: tres pestañas que conservan su estado.
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            TouristShellPage(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(routes: [
            GoRoute(
              path: '/explorar',
              name: 'explorar',
              builder: (context, state) => const ExplorePage(),
            ),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(
              path: '/favoritos',
              name: 'favoritos',
              builder: (context, state) => const FavoritesPage(),
            ),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(
              path: '/viajes',
              name: 'viajes',
              builder: (context, state) => const MyTripsPage(),
            ),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(
              path: '/asistente',
              name: 'asistente',
              builder: (context, state) => const AssistantPage(),
            ),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(
              path: '/perfil',
              name: 'perfil',
              builder: (context, state) => const ProfilePage(),
            ),
          ]),
        ],
      ),

      // Fichas del marketplace a pantalla completa. Se abren con push desde
      // Explorar o desde una recomendación del asistente.
      GoRoute(
        path: '/hospedaje/:id',
        name: 'hospedaje',
        builder: (context, state) =>
            LodgingDetailPage(lodgingId: int.tryParse(state.pathParameters['id'] ?? '') ?? 0),
      ),
      GoRoute(
        path: '/producto/:id',
        name: 'producto',
        builder: (context, state) =>
            ProductDetailPage(productId: int.tryParse(state.pathParameters['id'] ?? '') ?? 0),
      ),

      GoRoute(
        path: '/reserva/:id',
        name: 'reserva',
        builder: (context, state) =>
            BookingDetailPage(
          bookingId: int.tryParse(state.pathParameters['id'] ?? '') ?? 0,
          // situr-smart://app/reserva/ID?pago=exito al volver de Stripe.
          paymentResult: state.uri.queryParameters['pago'],
        ),
      ),

      GoRoute(
        path: '/itinerario/:id',
        name: 'itinerario',
        builder: (context, state) =>
            ItineraryDetailPage(itineraryId: int.tryParse(state.pathParameters['id'] ?? '') ?? 0),
      ),

      GoRoute(
        path: '/notificaciones',
        name: 'notificaciones',
        builder: (context, state) => const NotificationsInboxPage(),
      ),

      // El personal de empresas y el SuperAdmin administran desde la web: aquí
      // solo se les indica cómo llegar.
      GoRoute(
        path: '/panel-web',
        name: 'panel-web',
        builder: (context, state) => const StaffWebPanelPage(),
      ),
    ],
  );
}
