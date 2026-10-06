import '../../../core/network/api_client.dart';
import '../../../core/storage/token_storage.dart';

/// Datos del turista: auth/me/ para leerlos y PATCH auth/me/ para editarlos.
class ProfileService {
  final ApiClient _api = ApiClient();
  final TokenStorage _storage = TokenStorage();

  Future<Map<String, dynamic>> me() async {
    final user = await _api.getMap('auth/me/', '');
    await _storage.saveUser(user);
    return user;
  }

  /// Envía solo los campos editables; los vacíos viajan como null para que el
  /// backend borre el dato en lugar de guardar un texto vacío.
  Future<Map<String, dynamic>> update({
    required String nombres,
    required String apellidos,
    String? telefono,
    String? tipoDocumento,
    String? numeroDocumento,
    DateTime? fechaNacimiento,
  }) async {
    String? orNull(String? value) => (value == null || value.trim().isEmpty) ? null : value.trim();
    final user = await _api.patchAuth('auth/me/', {
      'nombres': nombres.trim(),
      'apellidos': apellidos.trim(),
      'telefono': orNull(telefono),
      'tipo_documento': orNull(tipoDocumento),
      'numero_documento': orNull(numeroDocumento),
      'fecha_nacimiento': fechaNacimiento == null
          ? null
          : '${fechaNacimiento.year.toString().padLeft(4, '0')}-'
              '${fechaNacimiento.month.toString().padLeft(2, '0')}-'
              '${fechaNacimiento.day.toString().padLeft(2, '0')}',
    });
    await _storage.saveUser(user);
    return user;
  }
}
