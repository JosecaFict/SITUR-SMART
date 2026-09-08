import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';


/// Gestiona el almacenamiento local de la sesión del usuario.
///
/// Guarda y recupera:
/// - Tokens JWT.
/// - Información del usuario autenticado.
class TokenStorage {

  static const String _accessToken = 'access_token';
  static const String _refreshToken = 'refresh_token';
  static const String _user = 'current_user';


  /// Guarda los tokens generados por el backend
  /// después de un inicio de sesión exitoso.
  ///
  /// Parámetros:
  /// - access: Token JWT utilizado para consumir APIs protegidas.
  /// - refresh: Token utilizado para renovar el access token.
  Future<void> saveTokens({
    required String access,
    required String refresh,
  }) async {

    final prefs = await SharedPreferences.getInstance();

    await prefs.setString(_accessToken, access);
    await prefs.setString(_refreshToken, refresh);

  }



  /// Guarda la información del usuario autenticado.
  ///
  /// Recibe el objeto usuario retornado por el backend
  /// y lo almacena localmente para utilizarlo
  /// en pantallas como Dashboard o Perfil.
  Future<void> saveUser(
    Map<String, dynamic> user,
  ) async {

    final prefs = await SharedPreferences.getInstance();

    await prefs.setString(
      _user,
      jsonEncode(user),
    );

  }



  /// Recupera la información del usuario actualmente
  /// autenticado.
  ///
  /// Retorna:
  /// - Map con los datos del usuario.
  /// - null si no existe información almacenada.
  Future<Map<String, dynamic>?> getUser() async {

    final prefs = await SharedPreferences.getInstance();

    final data = prefs.getString(_user);

    if (data == null) {
      return null;
    }

    return jsonDecode(data);

  }



  /// Obtiene el Access Token almacenado.
  ///
  /// Se utiliza para enviar autenticación
  /// en peticiones protegidas al backend.
  Future<String?> getAccessToken() async {

    final prefs = await SharedPreferences.getInstance();

    return prefs.getString(_accessToken);

  }



  /// Obtiene el Refresh Token almacenado.
  ///
  /// Permite renovar la sesión cuando el Access Token expire.
  Future<String?> getRefreshToken() async {

    final prefs = await SharedPreferences.getInstance();

    return prefs.getString(_refreshToken);

  }



  /// Elimina toda la información de sesión
  /// almacenada en el dispositivo.
  ///
  /// Se utiliza principalmente al cerrar sesión.
  Future<void> clearTokens() async {

    final prefs = await SharedPreferences.getInstance();

    await prefs.remove(_accessToken);
    await prefs.remove(_refreshToken);
    await prefs.remove(_user);

  }

}