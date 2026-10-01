import '../../../core/network/api_client.dart';
import '../../../core/storage/token_storage.dart';
import '../models/user.dart';

class UserService {
  final ApiClient _apiClient = ApiClient();
  final TokenStorage _storage = TokenStorage();

  Future<List<UserModel>> getUsers() async {
    final token = await _requiredToken();
    final tenantId = await _requiredTenantId();
    final response = await _apiClient.getList('usuarios/', token, tenantId: tenantId);
    return response.whereType<Map<String, dynamic>>().map(UserModel.fromJson).toList();
  }

  Future<UserModel> createUser({
    required String email,
    required String nombres,
    required String apellidos,
    String? telefono,
    required String estado,
    required String roleCode,
    required int tenantId,
  }) async {
    final response = await _apiClient.postAuth(
      'usuarios/',
      {
        'email': email,
        'first_names': nombres,
        'last_names': apellidos,
        'phone': telefono,
        'role_code': roleCode,
      },
      tenantId: tenantId,
    );
    return UserModel.fromJson(response);
  }

  Future<UserModel> updateUser(
    int id, {
    required String email,
    required String nombres,
    required String apellidos,
    String? telefono,
    required String estado,
  }) async {
    final tenantId = await _requiredTenantId();
    final response = await _apiClient.patchAuth(
      'usuarios/$id/',
      {
        'first_names': nombres,
        'last_names': apellidos,
        'phone': telefono,
      },
      tenantId: tenantId,
    );
    return UserModel.fromJson(response);
  }

  Future<void> deleteUser(int id) async {
    final tenantId = await _requiredTenantId();
    await _apiClient.deleteAuth('usuarios/$id/', tenantId: tenantId);
  }

  Future<String> _requiredToken() async {
    final token = await _storage.getAccessToken();
    if (token == null) throw const ApiException('No existe una sesión activa.');
    return token;
  }

  Future<int> _requiredTenantId() async {
    final tenantId = await _storage.getActiveTenantId();
    if (tenantId != null) return tenantId;

    if (await _storage.isSuperAdmin()) {
      final token = await _requiredToken();
      final companies = await _apiClient.getList('empresas/', token);
      if (companies.isNotEmpty && companies.first is Map) {
        final id = (companies.first as Map)['id'];
        if (id is int) return id;
        final parsed = int.tryParse(id.toString());
        if (parsed != null) return parsed;
      }
    }

    throw const ApiException('No existe una empresa disponible para gestionar usuarios.');
  }
}
