import '../../../core/network/api_client.dart';
import '../../../core/storage/token_storage.dart';


class AuthService {


  final ApiClient _apiClient =
      ApiClient();


  final TokenStorage _storage =
      TokenStorage();




  Future<Map<String, dynamic>> login({

    required String email,

    required String password,

  }) async {


    final response =
        await _apiClient.post(

      'auth/login/',

      {

        'email': email,

        'password': password,

      },

    );




    await _storage.saveTokens(

      access:
          response['access'],

      refresh:
          response['refresh'],

    );





    if(response['user'] != null){

      await _storage.saveUser(

        response['user'],

      );

    }



    return response;


  }


}