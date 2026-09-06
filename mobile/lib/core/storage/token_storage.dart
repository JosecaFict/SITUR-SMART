import 'package:shared_preferences/shared_preferences.dart';

class TokenStorage {

  static const String _accessToken = 'access_token';
  static const String _refreshToken = 'refresh_token';


  Future<void> saveTokens({
    required String access,
    required String refresh,
  }) async {

    final prefs = await SharedPreferences.getInstance();

    await prefs.setString(_accessToken, access);
    await prefs.setString(_refreshToken, refresh);
  }


  Future<String?> getAccessToken() async {

    final prefs = await SharedPreferences.getInstance();

    return prefs.getString(_accessToken);
  }


  Future<void> clearTokens() async {

    final prefs = await SharedPreferences.getInstance();

    await prefs.remove(_accessToken);
    await prefs.remove(_refreshToken);
  }
}