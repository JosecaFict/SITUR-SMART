import '../../../core/network/api_client.dart';
import '../../../core/storage/token_storage.dart';

import '../models/tenant.dart';


class TenantService {

  final ApiClient _apiClient = ApiClient();

  final TokenStorage _storage = TokenStorage();



  Future<String> _getToken() async {

    final token = await _storage.getAccessToken();

    if(token == null){
      throw Exception(
        'No existe token',
      );
    }

    return token;
  }




  Future<List<Tenant>> getTenants() async {


    final token = await _getToken();


    final data = await _apiClient.getList(
      'tenants/',
      token,
    );


    return data
        .map(
          (json)=>Tenant.fromJson(json),
        )
        .toList();

  }





  Future<Map<String,dynamic>> createTenant(
    Map<String,dynamic> body,
  ) async {


    final response = await _apiClient.postAuth(
      'tenants/',
      body,
    );


    return response;

  }





  Future<Map<String,dynamic>> updateTenant(
    int id,
    Map<String,dynamic> body,
  ) async {


    final response = await _apiClient.putAuth(
      'tenants/$id/',
      body,
    );


    return response;

  }





  Future<void> deleteTenant(
    int id,
  ) async {


    await _apiClient.deleteAuth(
      'tenants/$id/',
    );


  }


}