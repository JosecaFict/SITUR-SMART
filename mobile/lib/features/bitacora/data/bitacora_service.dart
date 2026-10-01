import '../../../core/network/api_client.dart';
import '../../../core/storage/token_storage.dart';
import '../models/bitacora.dart';

class BitacoraService {
  final ApiClient _apiClient = ApiClient();
  final TokenStorage _storage = TokenStorage();

  Future<List<Bitacora>> getBitacora() async {
    final token = await _apiClient.getAccessToken();
    if (token == null) throw const ApiException('No existe una sesión activa.');

    final tenantId = await _storage.getActiveTenantId();
    final response = await _apiClient.getMap(
      'bitacora/?limit=200',
      token,
      tenantId: tenantId,
    );
    final results = response['resultados'];
    if (results is! List) {
      throw const ApiException('La respuesta de bitácora no es válida.');
    }
    return results
        .whereType<Map<String, dynamic>>()
        .map(Bitacora.fromJson)
        .toList();
  }
}
