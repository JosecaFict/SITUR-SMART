import '../../../core/network/api_client.dart';
import '../../../core/storage/token_storage.dart';

import '../models/role.dart';



class RoleService {


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






  Future<List<RoleModel>> getRoles() async {


    final token =
        await _getToken();



    final response =
        await _apiClient.getList(

          'roles/',

          token,

        );



    return response

        .map(

          (json) => RoleModel.fromJson(json),

        )

        .toList();


  }



}