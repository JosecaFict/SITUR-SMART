import '../../../core/network/api_client.dart';

class AuthService {
  final ApiClient _apiClient = ApiClient();

  Future<Map<String, dynamic>> login({
    required String email,
    required String password,
  }) async {
    final response = await _apiClient.post(
      'auth/login/',
      {
        'email': email,
        'password': password,
      },
    );

    return response;
  }
}