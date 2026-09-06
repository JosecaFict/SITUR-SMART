import 'package:flutter/foundation.dart';

import '../../../core/network/api_client.dart';
import '../../../core/storage/token_storage.dart';

import '../models/user.dart';



class UserService {


  final ApiClient _apiClient = ApiClient();

  final TokenStorage _storage = TokenStorage();





  Future<String> _getToken() async {


    final token =
        await _storage.getAccessToken();


    if(token == null){

      throw Exception(
        'No existe token',
      );

    }


    return token;

  }








  Future<List<UserModel>> getUsers() async {


    final token =
        await _getToken();



    final response =
        await _apiClient.getMap(

          'auth/users/',

          token,

        );



    final results =
        response['results'] as List;



    return results

        .map(

          (json)=>

              UserModel.fromJson(json),

        )

        .toList();


  }








  Future<UserModel> createUser({


    required String email,

    required String nombres,

    required String apellidos,

    String? telefono,

    required String estado,

    required int roleId,

    required int tenantId,


  }) async {


    debugPrint("CREANDO USUARIO");
    debugPrint("ROLE ID: $roleId");
    debugPrint("TENANT ID: $tenantId");

    final response =

        await _apiClient.postAuth(

          'auth/users/',

          {


            'email': email,

            'nombres': nombres,

            'apellidos': apellidos,

            'telefono': telefono,

            'estado': estado,

            'role_id': roleId,

            'tenant_id': tenantId,


          },


        );



    return UserModel.fromJson(response);


  }









  Future<UserModel> updateUser(

    int id,

    {

    required String email,

    required String nombres,

    required String apellidos,

    String? telefono,

    required String estado,


    }

  ) async {



    final response =

        await _apiClient.putAuth(

          'auth/users/$id/',

          {


            'email': email,

            'nombres': nombres,

            'apellidos': apellidos,

            'telefono': telefono,

            'estado': estado,


          },


        );



    return UserModel.fromJson(response);


  }









  Future<void> deleteUser(

    int id,

  ) async {



    await _apiClient.deleteAuth(

      'auth/users/$id/',

    );


  }





}