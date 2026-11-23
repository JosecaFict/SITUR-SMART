import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

import '../../../core/network/api_client.dart';
import 'notifications_store.dart';

/// Notificaciones push con Firebase Cloud Messaging.
///
/// Con la app cerrada o en segundo plano, Android muestra el aviso solo (canal
/// "situr_avisos", ver MainActivity.kt). Con la app abierta llega a
/// [onForegroundMessage] y se avisa dentro de la app. Al tocar el aviso se
/// abre la reserva, la oferta o la bandeja de comunicaciones.
///
/// Toda app instalada se suscribe al tema "promociones" al arrancar, haya o
/// no sesión: así cualquier celular con el APK se entera de las ofertas.
///
/// El token del celular se registra en el backend (me/dispositivos/) al
/// iniciar sesión y se quita al cerrarla, para que el celular no siga
/// recibiendo avisos de una cuenta que ya salió.
class PushService {
  PushService._();

  static final PushService instance = PushService._();

  /// Mismo nombre que PROMOTIONS_TOPIC en backend/apps/notifications/push.py.
  static const promotionsTopic = 'promociones';

  /// Abre la ruta del aviso tocado.
  static void Function(String route)? onOpenRoute;

  /// Aviso recibido con la app abierta: Android no lo muestra solo.
  static void Function(String title, String body, String? route)?
  onForegroundMessage;

  final ApiClient _api = ApiClient();
  bool _ready = false;
  String? _registeredToken;
  StreamSubscription<String>? _tokenRefresh;

  /// Aviso que abrió la app desde cerrada. El splash lo abre después de
  /// restaurar la sesión, porque antes no hay a dónde navegar.
  String? _pendingRoute;

  String? takePendingRoute() {
    final route = _pendingRoute;
    _pendingRoute = null;
    return route;
  }

  /// Sin sesión solo se toma un destino público (una oferta); los demás se
  /// guardan para después del login.
  String? takePublicPendingRoute() {
    final route = _pendingRoute;
    if (route == null || !isPublicRoute(route)) return null;
    _pendingRoute = null;
    return route;
  }

  /// Destinos que se pueden abrir sin sesión.
  static bool isPublicRoute(String route) => route.startsWith('/promocion/');

  /// Si se necesita iniciar sesión, se conserva el destino para después.
  Future<void> openRoute(String route) async {
    final access = await _api.getAccessToken();
    final loggedIn = access != null && access.isNotEmpty;
    if (onOpenRoute == null || (!loggedIn && !isPublicRoute(route))) {
      _pendingRoute = route;
      return;
    }
    onOpenRoute?.call(route);
  }

  /// Las comunicaciones se leen en la bandeja, incluso si tienen reserva.
  /// Una oferta abre su detalle público.
  static String? routeFor(Map<String, dynamic> data) {
    if (data['tipo'] == 'COMUNICACION') return '/notificaciones';
    final promotion = int.tryParse('${data['promocion_id'] ?? ''}');
    if (promotion != null) return '/promocion/$promotion';
    final id = int.tryParse('${data['reserva_id'] ?? ''}');
    return id == null ? null : '/reserva/$id';
  }

  /// Se llama una vez al arrancar. Si Firebase no está disponible la app
  /// funciona igual: los avisos siguen en la bandeja.
  Future<void> init() async {
    try {
      await Firebase.initializeApp();
    } catch (error) {
      debugPrint('Push desactivado, Firebase no inició: $error');
      return;
    }
    _ready = true;

    FirebaseMessaging.onMessage.listen((message) {
      NotificationsStore.instance.refresh();
      final notification = message.notification;
      if (notification == null) return;
      onForegroundMessage?.call(
        notification.title ?? 'SITUR-SMART',
        notification.body ?? '',
        routeFor(message.data),
      );
    });
    FirebaseMessaging.onMessageOpenedApp.listen((message) {
      NotificationsStore.instance.refresh();
      final route = routeFor(message.data);
      if (route != null) openRoute(route);
    });
    try {
      final initial = await FirebaseMessaging.instance.getInitialMessage();
      _pendingRoute = initial == null ? null : routeFor(initial.data);
    } catch (_) {}
    // Sin await: el diálogo de permiso no debe frenar el arranque.
    unawaited(_subscribeToPromotions());
  }

  /// Toda app instalada recibe las ofertas del marketplace, con o sin sesión.
  /// Android 13+ pide el permiso aquí la primera vez que se abre la app.
  Future<void> _subscribeToPromotions() async {
    try {
      await FirebaseMessaging.instance.requestPermission();
      await FirebaseMessaging.instance.subscribeToTopic(promotionsTopic);
    } catch (error) {
      debugPrint('No se pudo suscribir a las ofertas: $error');
    }
  }

  /// Pide permiso (Android 13+ muestra el diálogo la primera vez) y registra
  /// el token del celular para la cuenta con sesión iniciada.
  Future<void> registerDevice() async {
    if (!_ready) return;
    try {
      final messaging = FirebaseMessaging.instance;
      final settings = await messaging.requestPermission();
      if (settings.authorizationStatus == AuthorizationStatus.denied) return;
      final token = await messaging.getToken();
      if (token != null) await _send(token);
      // Firebase puede rotar el token; el nuevo se registra solo.
      _tokenRefresh ??= messaging.onTokenRefresh.listen(_send);
    } catch (error) {
      debugPrint('No se pudo registrar el celular para push: $error');
    }
  }

  /// Al cerrar sesión, antes de revocar los tokens de la API.
  Future<void> unregisterDevice() async {
    _pendingRoute = null;
    if (!_ready) return;
    await _tokenRefresh?.cancel();
    _tokenRefresh = null;
    try {
      final token =
          _registeredToken ?? await FirebaseMessaging.instance.getToken();
      if (token != null) {
        await _api.postAuthEmpty(
          'me/dispositivos/quitar/',
          body: {'token': token},
        );
      }
    } catch (_) {
      // Sin red o sesión vencida: el backend lo reasigna en el próximo login.
    }
    _registeredToken = null;
  }

  Future<void> _send(String token) async {
    try {
      await _api.postAuthEmpty(
        'me/dispositivos/',
        body: {
          'token': token,
          'plataforma': defaultTargetPlatform == TargetPlatform.iOS
              ? 'IOS'
              : 'ANDROID',
        },
      );
      _registeredToken = token;
    } catch (error) {
      debugPrint('El backend no registró el celular para push: $error');
    }
  }
}
