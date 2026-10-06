import '../../../core/network/api_client.dart';
import '../../../core/storage/token_storage.dart';

import '../models/tenant.dart';


class TenantService {

  final ApiClient _apiClient = ApiClient();

  final TokenStorage _storage = TokenStorage();



  Future<String> _getToken() async {

    final token = await _storage.getAccessToken();

    if(token == null){
      throw Exception(
        'No existe token',
      );
    }

    return token;
  }




  Future<List<Tenant>> getTenants() async {
    final user = await _storage.getUser();
    final sessionTenants = user?['tenants'];
    if (sessionTenants is List && sessionTenants.isNotEmpty) {
      return sessionTenants.map((json) {
        final item = Map<String, dynamic>.from(json as Map);
        return Tenant(
          id: item['id'] as int,
          nombreComercial: item['name']?.toString() ?? '',
          razonSocial: item['name']?.toString() ?? '',
          estado: 'ACTIVO',
        );
      }).toList();
    }

    final token = await _getToken();
    final data = await _apiClient.getList('empresas/', token);
    return data
        .whereType<Map<String, dynamic>>()
        .map(Tenant.fromJson)
        .toList();

  }
}
