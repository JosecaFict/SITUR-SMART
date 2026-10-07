import 'dart:math';

import 'package:url_launcher/url_launcher.dart';

import '../../../core/network/api_client.dart';
import 'booking_models.dart';

class BookingService {
  BookingService({ApiClient? apiClient}) : _api = apiClient ?? ApiClient();

  final ApiClient _api;

  /// Precio y cupo, sin apartar nada.
  Future<BookingQuote> quote(BookingRequest request) async =>
      BookingQuote.fromJson(await _api.postAuth('me/reservas/cotizacion/', request.toJson()));

  /// Aparta el cupo y abre el pago. [idempotencyKey] evita reservar dos veces
  /// si el turista toca dos veces o la conexión obliga a reintentar.
  Future<Booking> create(BookingRequest request, {required String idempotencyKey}) async =>
      Booking.fromJson(
        await _api.postAuth(
          'me/reservas/',
          request.toJson(),
          extraHeaders: {'Idempotency-Key': idempotencyKey},
        ),
      );

  Future<List<Booking>> list() async {
    final data = await _api.getList('me/reservas/', '');
    return data.whereType<Map<String, dynamic>>().map(Booking.fromJson).toList();
  }

  /// Al consultarla, el backend la concilia con Stripe.
  Future<Booking> detail(int id) async => Booking.fromJson(await _api.getMap('me/reservas/$id/', ''));

  Future<String> checkoutUrl(int id) async {
    final data = await _api.postAuth('me/reservas/$id/pagar/', const {});
    return data['checkout_url'] as String;
  }

  /// Enlace firmado al comprobante PDF de una reserva pagada.
  Future<String> receiptUrl(int id) async {
    final data = await _api.getMap('me/reservas/$id/comprobante/', '');
    return data['url'] as String;
  }

  Future<Booking> cancel(int id) async =>
      Booking.fromJson(await _api.postAuth('me/reservas/$id/cancelar/', const {}));

  /// Abre la página de pago de Stripe dentro de la app (pestaña del navegador).
  static Future<bool> openCheckout(String url) =>
      launchUrl(Uri.parse(url), mode: LaunchMode.inAppBrowserView);

  static String newIdempotencyKey() {
    final random = Random.secure();
    return List.generate(16, (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
  }
}
