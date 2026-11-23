import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:go_router/go_router.dart';

import '../../features/asistente/presentation/assistant_page.dart';
import '../../features/favoritos/presentation/favorites_page.dart';
import '../../features/itinerarios/presentation/itinerary_detail_page.dart';
import '../../features/marketplace/presentation/explore_page.dart';
import '../../features/marketplace/presentation/lodging_detail_page.dart';
import '../../features/marketplace/presentation/product_detail_page.dart';
import '../../features/marketplace/presentation/promotion_detail_page.dart';
import '../../features/notificaciones/presentation/notifications_page.dart';
import '../../features/pagos/presentation/my_payments_page.dart';
import '../../features/perfil/presentation/profile_page.dart';
import '../../features/reservas/presentation/booking_detail_page.dart';
import '../../features/reservas/presentation/my_trips_page.dart';
import '../../features/turista/tourist_shell_page.dart';
import '../../features/usuarios/data/auth_service.dart';
import '../../features/usuarios/presentation/pages/forgot_password_page.dart';
import '../../features/usuarios/presentation/pages/login_page.dart';
import '../../features/usuarios/presentation/pages/register_page.dart';
import '../../features/usuarios/presentation/pages/splash_page.dart';
import '../../features/usuarios/presentation/pages/staff_web_panel_page.dart';
import '../storage/token_storage.dart';

class AppRouter {
  AppRouter._();

  /// Espera a que el inicio pase los guards antes de apilar el destino push.
  /// Un go y un push inmediatos pueden dejar el login debajo de la bandeja.
  /// Devuelve una cancelación para dispose; otra navegación también la cancela.
  static VoidCallback openHome(
    GoRouter router,
    Map<String, dynamic>? user, {
    String? pendingRoute,
    String? homeRoute,
  }) {
    final home = homeRoute ?? AuthService.homeRouteFor(user);
    if (pendingRoute == null) {
      router.go(home);
      return () {};
    }
    if (router.routerDelegate.currentConfiguration.uri.path == home) {
      router.push(pendingRoute);
      return () {};
    }
    var active = true;
    Timer? deadline;
    late final VoidCallback onSettled;
    late final VoidCallback onRequested;
    void cancel() {
      if (!active) return;
      active = false;
      deadline?.cancel();
      router.routerDelegate.removeListener(onSettled);
      router.routeInformationProvider.removeListener(onRequested);
    }

    onSettled = () {
      final reachedHome =
          router.routerDelegate.currentConfiguration.uri.path == home;
      cancel();
      if (reachedHome) router.push(pendingRoute);
    };
    onRequested = () {
      if (router.routeInformationProvider.value.uri.path != home) cancel();
    };
    router.routerDelegate.addListener(onSettled);
    router.routeInformationProvider.addListener(onRequested);
    // Un guard bloqueado o que conserva la ruta actual puede no notificar.
    deadline = Timer(const Duration(seconds: 30), cancel);
    try {
      router.go(home);
    } catch (_) {
      cancel();
      rethrow;
    }
    return cancel;
  }

  /// El personal puede recibir avisos sin entrar a las pantallas del turista.
  static Future<String?> redirectFor(Uri uri) async {
    final path = uri.path;
    if (const {
      '/',
      '/login',
      '/registrar-usuario',
      '/recuperar-password',
    }.contains(path)) {
      return null;
    }
    final storage = TokenStorage();
    final access = await storage.getAccessToken();
    if (access == null || access.isEmpty) {
      return path == '/notificaciones' || path == '/panel-web'
          ? '/login'
          : null;
    }
    final staff = AuthService.isStaff(await storage.getUser());
    if (staff && path != '/panel-web' && path != '/notificaciones') {
      return '/panel-web';
    }
    if (!staff && path == '/panel-web') return '/explorar';
    return null;
  }

  static final GoRouter router = GoRouter(
    initialLocation: '/',
    redirect: (context, state) => redirectFor(state.uri),
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
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/explorar',
                name: 'explorar',
                builder: (context, state) => const ExplorePage(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/favoritos',
                name: 'favoritos',
                builder: (context, state) => const FavoritesPage(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/viajes',
                name: 'viajes',
                builder: (context, state) => const MyTripsPage(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/asistente',
                name: 'asistente',
                builder: (context, state) => const AssistantPage(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/perfil',
                name: 'perfil',
                builder: (context, state) => const ProfilePage(),
              ),
            ],
          ),
        ],
      ),

      // Fichas del marketplace a pantalla completa. Se abren con push desde
      // Explorar o desde una recomendación del asistente.
      GoRoute(
        path: '/hospedaje/:id',
        name: 'hospedaje',
        builder: (context, state) => LodgingDetailPage(
          lodgingId: int.tryParse(state.pathParameters['id'] ?? '') ?? 0,
        ),
      ),
      GoRoute(
        path: '/producto/:id',
        name: 'producto',
        builder: (context, state) => ProductDetailPage(
          productId: int.tryParse(state.pathParameters['id'] ?? '') ?? 0,
        ),
      ),

      // Oferta abierta desde su push; pública, sirve sin sesión.
      GoRoute(
        path: '/promocion/:id',
        name: 'promocion',
        builder: (context, state) => PromotionDetailPage(
          promotionId: int.tryParse(state.pathParameters['id'] ?? '') ?? 0,
        ),
      ),

      GoRoute(
        path: '/reserva/:id',
        name: 'reserva',
        builder: (context, state) => BookingDetailPage(
          bookingId: int.tryParse(state.pathParameters['id'] ?? '') ?? 0,
          // situr-smart://app/reserva/ID?pago=exito al volver de Stripe.
          paymentResult: state.uri.queryParameters['pago'],
        ),
      ),

      GoRoute(
        path: '/itinerario/:id',
        name: 'itinerario',
        builder: (context, state) => ItineraryDetailPage(
          itineraryId: int.tryParse(state.pathParameters['id'] ?? '') ?? 0,
        ),
      ),

      GoRoute(
        path: '/notificaciones',
        name: 'notificaciones',
        builder: (context, state) => const NotificationsInboxPage(),
      ),

      GoRoute(
        path: '/pagos',
        name: 'pagos',
        builder: (context, state) => const MyPaymentsPage(),
      ),

      // El personal recibe comunicaciones aquí; administra desde la web.
      GoRoute(
        path: '/panel-web',
        name: 'panel-web',
        builder: (context, state) => const StaffWebPanelPage(),
      ),
    ],
  );
}
