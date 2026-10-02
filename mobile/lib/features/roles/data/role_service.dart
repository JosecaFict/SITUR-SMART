import '../../../core/network/api_client.dart';
import '../../../core/storage/token_storage.dart';
import '../models/role.dart';

class RoleService {
  final ApiClient _apiClient = ApiClient();
  final TokenStorage _storage = TokenStorage();

  Future<List<Role>> getRoles() async {
    final token = await _apiClient.getAccessToken();
    if (token == null) throw const ApiException('No existe una sesión activa.');
    final tenantId = await _storage.getActiveTenantId();
    final response = await _apiClient.getList('roles/', token, tenantId: tenantId);
    return response.whereType<Map<String, dynamic>>().map(Role.fromJson).toList();
  }

  Future<Role> getRole(int id) async {
    final token = await _apiClient.getAccessToken();
    if (token == null) throw const ApiException('No existe una sesión activa.');
    final tenantId = await _requiredTenantId();
    final response = await _apiClient.getMap('roles/$id/', token, tenantId: tenantId);
    return Role.fromJson(response);
  }

  Future<Role> createRole(Map<String, dynamic> data) async {
    final tenantId = await _requiredTenantId();
    final response = await _apiClient.postAuth('roles/', data, tenantId: tenantId);
    return Role.fromJson(response);
  }

  Future<Role> updateRole(int id, Map<String, dynamic> data) async {
    final tenantId = await _requiredTenantId();
    final response = await _apiClient.patchAuth('roles/$id/', data, tenantId: tenantId);
    return Role.fromJson(response);
  }

  Future<void> deleteRole(int id) async {
    final tenantId = await _requiredTenantId();
    await _apiClient.deleteAuth('roles/$id/', tenantId: tenantId);
  }

  Future<int> _requiredTenantId() async {
    final tenantId = await _storage.getActiveTenantId();
    if (tenantId == null) {
      throw const ApiException('Selecciona una empresa para gestionar sus roles.');
    }
    return tenantId;
  }
}
