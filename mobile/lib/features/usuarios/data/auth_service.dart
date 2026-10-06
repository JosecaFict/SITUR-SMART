import '../../../core/network/api_client.dart';
import '../../../core/storage/token_storage.dart';
import '../../favoritos/data/favorites_store.dart';

/// Autenticación contra la API: login, registro de turistas, cierre de sesión,
/// restauración de la sesión guardada y recuperación de contraseña por OTP.
class AuthService {
  final ApiClient _apiClient = ApiClient();
  final TokenStorage _storage = TokenStorage();

  Future<Map<String, dynamic>> login({
    required String email,
    required String password,
  }) async {
    final response = await _apiClient.post('auth/login/', {
      'email': email,
      'password': password,
    });
    await _saveSession(response);
    return response;
  }

  /// Registra un turista (rol CLIENTE). El backend devuelve la sesión iniciada.
  Future<Map<String, dynamic>> register({
    required String nombres,
    required String apellidos,
    required String email,
    required String password,
    String? telefono,
  }) async {
    final response = await _apiClient.post('auth/register/', {
      'nombres': nombres,
      'apellidos': apellidos,
      'email': email,
      'password': password,
      if (telefono != null && telefono.isNotEmpty) 'telefono': telefono,
    });
    await _saveSession(response);
    return response;
  }

  /// Revoca el refresh token en el backend y borra la sesión local. La sesión
  /// local se borra aunque el backend no responda.
  Future<void> logout() async {
    final refresh = await _storage.getRefreshToken();
    try {
      if (refresh != null && refresh.isNotEmpty) {
        await _apiClient.post('auth/logout/', {'refresh': refresh});
      }
    } catch (_) {
      // Sin conexión o refresh ya vencido: igual se cierra la sesión local.
    } finally {
      await _storage.clearTokens();
      FavoritesStore.instance.clear();
    }
  }

  /// Al abrir la app: si hay una sesión guardada, la renueva y devuelve el
  /// usuario; si no hay o ya no es válida, devuelve null.
  Future<Map<String, dynamic>?> restoreSession() async {
    final refresh = await _storage.getRefreshToken();
    if (refresh == null || refresh.isEmpty) return null;
    final access = await _apiClient.refreshSession();
    if (access == null) return null;
    return _storage.getUser();
  }

  /// Paso 1: pide el código de 6 dígitos. La respuesta es la misma exista o no
  /// la cuenta, para no revelar qué correos están registrados.
  Future<String> requestPasswordReset(String email) async {
    final response = await _apiClient.post('auth/password-reset/request/', {'email': email});
    return (response['detail'] as String?) ??
        'Si el correo está registrado, recibirás un código de verificación.';
  }

  /// Paso 2: comprueba el código antes de pedir la nueva contraseña.
  Future<void> verifyPasswordResetCode({required String email, required String code}) async {
    await _apiClient.post('auth/password-reset/verify/', {'email': email, 'code': code});
  }

  /// Paso 3: fija la nueva contraseña. El backend cierra todas las sesiones
  /// abiertas de esa cuenta.
  Future<String> confirmPasswordReset({
    required String email,
    required String code,
    required String newPassword,
  }) async {
    final response = await _apiClient.post('auth/password-reset/confirm/', {
      'email': email,
      'code': code,
      'new_password': newPassword,
      'new_password_confirm': newPassword,
    });
    return (response['detail'] as String?) ?? 'Tu contraseña fue restablecida.';
  }

  Future<void> _saveSession(Map<String, dynamic> response) async {
    // Una cuenta nueva no hereda las marcas de la anterior.
    FavoritesStore.instance.clear();
    await _storage.saveTokens(
      access: response['access'] as String,
      refresh: response['refresh'] as String,
    );
    if (response['user'] is Map<String, dynamic>) {
      await _storage.saveUser(response['user'] as Map<String, dynamic>);
    }
  }

  /// Ruta de inicio según el usuario: los turistas van a Explorar y el
  /// personal de empresas y el SuperAdmin al panel.
  static String homeRouteFor(Map<String, dynamic>? user) {
    final roles = user?['roles'];
    final tenants = user?['tenants'];
    final isStaff = (roles is List && roles.contains('SUPER_ADMIN')) ||
        (tenants is List && tenants.isNotEmpty);
    return isStaff ? '/dashboard' : '/explorar';
  }
}
