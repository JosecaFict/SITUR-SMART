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

  /// GET a un endpoint público (marketplace, catálogos). Va sin token a
  /// propósito: con un access vencido el backend respondería 401 aunque la
  /// vista sea pública. Los parámetros nulos o vacíos no se envían.
  Future<dynamic> getPublic(
    String endpoint, {
    Map<String, Object?> query = const {},
  }) async {
    final params = <String, String>{
      for (final entry in query.entries)
        if (entry.value != null && entry.value.toString().isNotEmpty)
          entry.key: entry.value.toString(),
    };
    final uri = _uri(endpoint);
    final response = await http.get(
      params.isEmpty ? uri : uri.replace(queryParameters: params),
      headers: const {'Accept': 'application/json'},
    );
    return _decode(response);
  }

  /// Sube un archivo como multipart/form-data con la sesión iniciada.
  Future<Map<String, dynamic>> postFileAuth(
    String endpoint, {
    required String field,
    required String filePath,
  }) async {
    final response = await _authorized((accessToken) async {
      final request = http.MultipartRequest('POST', _uri(endpoint))
        ..headers['Authorization'] = 'Bearer $accessToken'
        ..files.add(await http.MultipartFile.fromPath(field, filePath));
      return http.Response.fromStream(await request.send());
    });
    return _decodeMap(response);
  }

  Future<List<dynamic>> getList(
    String endpoint,
    String token, {
    int? tenantId,
    Map<String, String> extraHeaders = const {},
  }) async {
    final response = await _authorized(
      (accessToken) => http.get(
        _uri(endpoint),
        headers: {..._headers(token: accessToken, tenantId: tenantId), ...extraHeaders},
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
    Map<String, String> extraHeaders = const {},
  }) async {
    final response = await _authorized(
      (accessToken) => http.post(
        _uri(endpoint),
        headers: {..._headers(token: accessToken, tenantId: tenantId), ...extraHeaders},
        body: jsonEncode(body),
      ),
    );
    return _decodeMap(response);
  }

  /// POST autenticado cuya respuesta puede venir vacía (204).
  Future<void> postAuthEmpty(String endpoint, {Map<String, dynamic> body = const {}}) async {
    final response = await _authorized(
      (accessToken) => http.post(
        _uri(endpoint),
        headers: _headers(token: accessToken),
        body: jsonEncode(body),
      ),
    );
    _decode(response, allowEmpty: true);
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
      throw ApiException(_errorMessage(response), statusCode: response.statusCode, code: _errorCode(response));
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

  /// Código estable del error (p. ej. `correo_no_verificado`), si el backend lo manda.
  String? _errorCode(http.Response response) {
    try {
      final data = jsonDecode(utf8.decode(response.bodyBytes));
      if (data is Map<String, dynamic> && data['error'] is Map<String, dynamic>) {
        final code = (data['error'] as Map<String, dynamic>)['code'];
        return code is String ? code : null;
      }
    } on FormatException {
      // Sin código.
    }
    return null;
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
  const ApiException(this.message, {this.statusCode, this.code});

  final String message;
  final int? statusCode;

  /// Código del error que manda el backend, para reaccionar sin leer el texto.
  final String? code;

  @override
  String toString() => message;
}
