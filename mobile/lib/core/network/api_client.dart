import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../storage/token_storage.dart';

class ApiClient {
  static const String baseUrl = String.fromEnvironment(
    'API_URL',
    defaultValue: 'http://10.0.2.2:8000/api/v1/',
  );

  /// Se ejecuta cuando la sesión no puede renovarse (refresh vencido o
  /// revocado). La app lo usa para volver al login.
  static void Function()? onSessionExpired;

  /// Renovación en curso. El backend rota el refresh token: cada uso invalida
  /// el anterior, así que si varias peticiones reciben 401 a la vez todas deben
  /// esperar a la misma renovación en lugar de lanzar una cada una.
  static Future<String?>? _refreshing;

  final TokenStorage _storage = TokenStorage();

  Future<String?> getAccessToken() => _storage.getAccessToken();

  Future<Map<String, dynamic>> post(
    String endpoint,
    Map<String, dynamic> body,
  ) async {
    final response = await http.post(
      _uri(endpoint),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    return _decodeMap(response);
  }

  Future<List<dynamic>> getList(
    String endpoint,
    String token, {
    int? tenantId,
  }) async {
    final response = await _authorized(
      (accessToken) => http.get(
        _uri(endpoint),
        headers: _headers(token: accessToken, tenantId: tenantId),
      ),
      token: token,
    );
    final data = _decode(response);
    if (data is List<dynamic>) return data;
    throw const ApiException('El backend no devolvió una lista válida.');
  }

  Future<Map<String, dynamic>> getMap(
    String endpoint,
    String token, {
    int? tenantId,
  }) async {
    final response = await _authorized(
      (accessToken) => http.get(
        _uri(endpoint),
        headers: _headers(token: accessToken, tenantId: tenantId),
      ),
      token: token,
    );
    return _decodeMap(response);
  }

  Future<Map<String, dynamic>> postAuth(
    String endpoint,
    Map<String, dynamic> body, {
    int? tenantId,
  }) async {
    final response = await _authorized(
      (accessToken) => http.post(
        _uri(endpoint),
        headers: _headers(token: accessToken, tenantId: tenantId),
        body: jsonEncode(body),
      ),
    );
    return _decodeMap(response);
  }

  Future<Map<String, dynamic>> patchAuth(
    String endpoint,
    Map<String, dynamic> body, {
    int? tenantId,
  }) async {
    final response = await _authorized(
      (accessToken) => http.patch(
        _uri(endpoint),
        headers: _headers(token: accessToken, tenantId: tenantId),
        body: jsonEncode(body),
      ),
    );
    return _decodeMap(response);
  }

  Future<Map<String, dynamic>> putAuth(
    String endpoint,
    Map<String, dynamic> body, {
    int? tenantId,
  }) async {
    final response = await _authorized(
      (accessToken) => http.put(
        _uri(endpoint),
        headers: _headers(token: accessToken, tenantId: tenantId),
        body: jsonEncode(body),
      ),
    );
    return _decodeMap(response);
  }

  Future<void> deleteAuth(String endpoint, {int? tenantId}) async {
    final response = await _authorized(
      (accessToken) => http.delete(
        _uri(endpoint),
        headers: _headers(token: accessToken, tenantId: tenantId),
      ),
    );
    _decode(response, allowEmpty: true);
  }

  /// Renueva el access token con el refresh guardado y devuelve el nuevo, o
  /// null si la sesión ya no se puede renovar.
  Future<String?> refreshSession() {
    return _refreshing ??= _doRefresh().whenComplete(() {
      _refreshing = null;
    });
  }

  Future<String?> _doRefresh() async {
    final refresh = await _storage.getRefreshToken();
    if (refresh == null || refresh.isEmpty) return null;
    try {
      final response = await http.post(
        _uri('auth/refresh/'),
        headers: const {'Content-Type': 'application/json'},
        body: jsonEncode({'refresh': refresh}),
      );
      if (response.statusCode < 200 || response.statusCode >= 300) {
        // 401: refresh vencido o revocado. Cualquier otro código tampoco
        // deja una sesión usable.
        await _storage.clearTokens();
        return null;
      }
      final data = jsonDecode(utf8.decode(response.bodyBytes));
      if (data is! Map<String, dynamic>) return null;
      await _storage.saveTokens(
        access: data['access'] as String,
        refresh: data['refresh'] as String,
      );
      if (data['user'] is Map<String, dynamic>) {
        await _storage.saveUser(data['user'] as Map<String, dynamic>);
      }
      return data['access'] as String;
    } on http.ClientException {
      // Sin conexión: no se borra la sesión, puede funcionar al reintentar.
      return null;
    } on FormatException {
      return null;
    }
  }

  /// Envía una petición autenticada. Si el access token venció (401), renueva
  /// la sesión una vez y reintenta; si no se puede renovar, avisa a la app.
  Future<http.Response> _authorized(
    Future<http.Response> Function(String accessToken) send, {
    String? token,
  }) async {
    final accessToken =
        (token != null && token.isNotEmpty) ? token : await _requiredToken();
    final response = await send(accessToken);
    if (response.statusCode != 401) return response;

    final renewed = await refreshSession();
    if (renewed == null) {
      if (await _storage.getRefreshToken() == null) {
        onSessionExpired?.call();
      }
      throw const ApiException(
        'La sesión ha finalizado. Inicia sesión nuevamente.',
        statusCode: 401,
      );
    }
    return send(renewed);
  }

  Uri _uri(String endpoint) {
    final normalizedBase = baseUrl.endsWith('/') ? baseUrl : '$baseUrl/';
    final normalizedEndpoint = endpoint.startsWith('/') ? endpoint.substring(1) : endpoint;
    return Uri.parse('$normalizedBase$normalizedEndpoint');
  }

  Map<String, String> _headers({String? token, int? tenantId}) => {
        'Content-Type': 'application/json',
        if (token != null && token.isNotEmpty) 'Authorization': 'Bearer $token',
        if (tenantId != null) 'X-Tenant-ID': tenantId.toString(),
      };

  Future<String> _requiredToken() async {
    final token = await _storage.getAccessToken();
    if (token == null || token.isEmpty) {
      throw const ApiException('La sesión ha finalizado. Inicia sesión nuevamente.');
    }
    return token;
  }

  dynamic _decode(http.Response response, {bool allowEmpty = false}) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(_errorMessage(response), statusCode: response.statusCode);
    }
    if (allowEmpty && response.body.trim().isEmpty) return null;
    try {
      return jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw const ApiException('El backend devolvió una respuesta no válida.');
    }
  }

  Map<String, dynamic> _decodeMap(http.Response response) {
    final data = _decode(response);
    if (data is Map<String, dynamic>) return data;
    throw const ApiException('El backend no devolvió un objeto válido.');
  }

  String _errorMessage(http.Response response) {
    try {
      final data = jsonDecode(utf8.decode(response.bodyBytes));
      if (data is Map<String, dynamic>) {
        final error = data['error'];
        if (error is Map<String, dynamic> && error['message'] is String) {
          return error['message'] as String;
        }
        if (data['detail'] is String) return data['detail'] as String;
      }
    } on FormatException {
      // Se usa el mensaje genérico de abajo.
    }
    return 'No fue posible completar la solicitud (${response.statusCode}).';
  }
}

class ApiException implements Exception {
  const ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}
