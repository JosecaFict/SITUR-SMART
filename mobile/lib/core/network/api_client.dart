import 'dart:convert';

import 'package:http/http.dart' as http;

import '../storage/token_storage.dart';

class ApiClient {
  static const String baseUrl = String.fromEnvironment(
    'API_URL',
    defaultValue: 'http://10.0.2.2:8000/api/v1/',
  );

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
    final response = await http.get(
      _uri(endpoint),
      headers: _headers(token: token, tenantId: tenantId),
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
    final response = await http.get(
      _uri(endpoint),
      headers: _headers(token: token, tenantId: tenantId),
    );
    return _decodeMap(response);
  }

  Future<Map<String, dynamic>> postAuth(
    String endpoint,
    Map<String, dynamic> body, {
    int? tenantId,
  }) async {
    final token = await _requiredToken();
    final response = await http.post(
      _uri(endpoint),
      headers: _headers(token: token, tenantId: tenantId),
      body: jsonEncode(body),
    );
    return _decodeMap(response);
  }

  Future<Map<String, dynamic>> patchAuth(
    String endpoint,
    Map<String, dynamic> body, {
    int? tenantId,
  }) async {
    final token = await _requiredToken();
    final response = await http.patch(
      _uri(endpoint),
      headers: _headers(token: token, tenantId: tenantId),
      body: jsonEncode(body),
    );
    return _decodeMap(response);
  }

  Future<Map<String, dynamic>> putAuth(
    String endpoint,
    Map<String, dynamic> body, {
    int? tenantId,
  }) async {
    final token = await _requiredToken();
    final response = await http.put(
      _uri(endpoint),
      headers: _headers(token: token, tenantId: tenantId),
      body: jsonEncode(body),
    );
    return _decodeMap(response);
  }

  Future<void> deleteAuth(String endpoint, {int? tenantId}) async {
    final token = await _requiredToken();
    final response = await http.delete(
      _uri(endpoint),
      headers: _headers(token: token, tenantId: tenantId),
    );
    _decode(response, allowEmpty: true);
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
      return jsonDecode(response.body);
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
      final data = jsonDecode(response.body);
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
