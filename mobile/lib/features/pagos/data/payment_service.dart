import '../../../core/network/api_client.dart';
import 'payment_models.dart';

class PaymentService {
  PaymentService({ApiClient? apiClient}) : _api = apiClient ?? ApiClient();
  final ApiClient _api;

  Future<List<PaymentMovement>> mine() async {
    final data = await _api.getMap('me/pagos/?page_size=100', '');
    return (data['results'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(PaymentMovement.fromJson)
        .toList();
  }
}
