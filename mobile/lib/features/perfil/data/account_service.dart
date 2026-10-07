import '../../../core/network/api_client.dart';
import '../../../core/storage/token_storage.dart';

/// Una sesión abierta de la cuenta (auth/me/sesiones/).
class AccountSession {
  const AccountSession({
    required this.id,
    required this.device,
    required this.startedAt,
    required this.current,
    this.ip,
  });

  final int id;
  final String device;
  final String? ip;
  final DateTime startedAt;

  /// Es la de este celular.
  final bool current;

  factory AccountSession.fromJson(Map<String, dynamic> json) => AccountSession(
        id: json['id'] is int ? json['id'] as int : int.tryParse('${json['id']}') ?? 0,
        device: json['dispositivo']?.toString() ?? 'Dispositivo',
        ip: json['ip']?.toString(),
        startedAt: DateTime.tryParse('${json['iniciada_en'] ?? ''}')?.toLocal() ?? DateTime(1970),
        current: json['actual'] == true,
      );
}

/// Seguridad de la cuenta: correo, contraseña, sesiones y baja.
class AccountService {
  AccountService({ApiClient? apiClient}) : _api = apiClient ?? ApiClient();

  final ApiClient _api;
  final TokenStorage _storage = TokenStorage();

  /// Envía (o reenvía) el código de 6 dígitos al correo.
  Future<void> sendEmailCode() => _api.postAuthEmpty('auth/correo/enviar-codigo/');

  Future<void> confirmEmail(String code) async {
    final user = await _api.postAuth('auth/correo/verificar/', {'codigo': code.trim()});
    await _storage.saveUser(user);
  }

  /// Cambia la contraseña. El backend cierra las demás sesiones y le da a
  /// este celular tokens nuevos.
  Future<void> changePassword({required String current, required String next}) async {
    final tokens = await _api.postAuth('auth/me/contrasena/', {'actual': current, 'nueva': next});
    await _storage.saveTokens(access: tokens['access'] as String, refresh: tokens['refresh'] as String);
  }

  Future<List<AccountSession>> sessions() async {
    final refresh = await _storage.getRefreshToken();
    final data = await _api.getList(
      'auth/me/sesiones/',
      '',
      extraHeaders: {'X-Refresh-Token': ?refresh},
    );
    return data.whereType<Map<String, dynamic>>().map(AccountSession.fromJson).toList();
  }

  Future<void> closeSession(int id) => _api.postAuthEmpty('auth/me/sesiones/$id/cerrar/');

  Future<int> closeOtherSessions() async {
    final refresh = await _storage.getRefreshToken() ?? '';
    final data = await _api.postAuth('auth/me/sesiones/cerrar-otras/', {'refresh': refresh});
    return data['cerradas'] is int ? data['cerradas'] as int : 0;
  }

  /// Baja de la cuenta: el backend la anonimiza. Luego se borra la sesión local.
  Future<void> deleteAccount(String password) async {
    await _api.postAuthEmpty('auth/me/eliminar/', body: {'password': password});
    await _storage.clearTokens();
  }
}
