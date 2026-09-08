import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../storage/token_storage.dart';


class ApiClient {

  static const String baseUrl =
      'http://192.168.137.1:8000/api/v1/';


  final TokenStorage _storage = TokenStorage();

  /// Obtiene el token actual almacenado.
  Future<String?> getAccessToken() async {

  return await _storage.getAccessToken();

  }



  Future<Map<String, dynamic>> post(
    String endpoint,
    Map<String, dynamic> body,
  ) async {

    debugPrint("POST URL: ${baseUrl + endpoint}");
debugPrint("BODY: ${jsonEncode(body)}");

    final response = await http.post(

      Uri.parse('$baseUrl$endpoint'),

      headers: {
        'Content-Type': 'application/json',
      },

      body: jsonEncode(body),

    );


    return _handleResponse(response);

  }





  Future<List<dynamic>> getList(
    String endpoint,
    String token,
  ) async {


    final response = await http.get(

      Uri.parse('$baseUrl$endpoint'),

      headers: {

        'Authorization': 'Bearer $token',

        'Content-Type': 'application/json',

      },

    );


    debugPrint('URL: ${response.request?.url}');
debugPrint('STATUS: ${response.statusCode}');

final bodyPreview = response.body.length > 300
    ? response.body.substring(0, 300)
    : response.body;

debugPrint('BODY: $bodyPreview');


    if(response.statusCode == 200){

      return jsonDecode(response.body)
          as List<dynamic>;

    }


    throw Exception(
      'Error al obtener datos',
    );

  }

Future<Map<String, dynamic>> getMap(
  String endpoint,
  String token,
) async {


  final response = await http.get(

    Uri.parse('$baseUrl$endpoint'),

    headers: {

      'Authorization': 'Bearer $token',

      'Content-Type': 'application/json',

    },

  );



  debugPrint('URL: ${response.request?.url}');
debugPrint('STATUS: ${response.statusCode}');

final bodyPreview = response.body.length > 300
    ? response.body.substring(0, 300)
    : response.body;

debugPrint('BODY: $bodyPreview');



  if(response.statusCode == 200){

    return jsonDecode(
      response.body,
    );

  }


  throw Exception(
    'Error al obtener usuarios',
  );


}




  Future<Map<String,dynamic>> postAuth(
    String endpoint,
    Map<String,dynamic> body,
  ) async {


    final token = await _storage.getAccessToken();


    final response = await http.post(

      Uri.parse('$baseUrl$endpoint'),

      headers: {

        'Authorization': 'Bearer $token',

        'Content-Type': 'application/json',

      },


      body: jsonEncode(body),

    );


    return _handleResponse(response);

  }







  Future<Map<String,dynamic>> putAuth(
    String endpoint,
    Map<String,dynamic> body,
  ) async {


    final token = await _storage.getAccessToken();


    final response = await http.put(

      Uri.parse('$baseUrl$endpoint'),

      headers: {

        'Authorization': 'Bearer $token',

        'Content-Type': 'application/json',

      },


      body: jsonEncode(body),

    );


    return _handleResponse(response);

  }







  Future<void> deleteAuth(
    String endpoint,
  ) async {


    final token = await _storage.getAccessToken();


    final response = await http.delete(

      Uri.parse('$baseUrl$endpoint'),

      headers: {

        'Authorization': 'Bearer $token',

        'Content-Type': 'application/json',

      },

    );


    if(response.statusCode < 200 ||
       response.statusCode >= 300){

      throw Exception(
        'Error al eliminar registro',
      );

    }

  }







  
  Map<String,dynamic> _handleResponse(
    http.Response response,
  ) {

    debugPrint("STATUS: ${response.statusCode}");

    final bodyPreview = response.body.length > 1000
        ? response.body.substring(0,1000)
        : response.body;

    debugPrint("RESPONSE:");
    debugPrint(bodyPreview);

    
    final data = jsonDecode(
      response.body,
    );


    if(response.statusCode >= 200 &&
       response.statusCode < 300){

      return data;

    }


    throw Exception(
  response.body,
);

  }

}