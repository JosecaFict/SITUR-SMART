import '../../../core/network/api_client.dart';

import '../models/role.dart';


/// Servicio encargado de gestionar los roles.
///
/// Se comunica con el backend Django REST
/// utilizando el ApiClient central del proyecto.
class RoleService {


  final ApiClient _apiClient =
      ApiClient();



  /// Obtiene todos los roles registrados.
  ///
  /// Endpoint:
  /// GET roles/
  Future<List<Role>> getRoles() async {


    final token =
        await _apiClient.getAccessToken() ?? '';



    final response =
        await _apiClient.getList(
          'roles/',
          token,
        );



    return response
        .map(
          (json) =>
              Role.fromJson(
                json,
              ),
        )
        .toList();

  }





  /// Obtiene un rol específico por ID.
  ///
  /// Endpoint:
  /// GET roles/{id}/
  Future<Role> getRole(
    int id,
  ) async {


    final token =
        await _apiClient.getAccessToken() ?? '';



    final response =
        await _apiClient.getMap(
          'roles/$id/',
          token,
        );



    return Role.fromJson(
      response,
    );

  }





  /// Crea un nuevo rol.
  ///
  /// Endpoint:
  /// POST roles/
  Future<Role> createRole(
    Map<String, dynamic> data,
  ) async {


    final response =
        await _apiClient.postAuth(
          'roles/',
          data,
        );



    return Role.fromJson(
      response,
    );

  }





  /// Actualiza un rol existente.
  ///
  /// Endpoint:
  /// PUT roles/{id}/
  Future<Role> updateRole(
    int id,
    Map<String, dynamic> data,
  ) async {


    final response =
        await _apiClient.putAuth(
          'roles/$id/',
          data,
        );



    return Role.fromJson(
      response,
    );

  }





  /// Elimina un rol.
  ///
  /// Endpoint:
  /// DELETE roles/{id}/
  Future<void> deleteRole(
    int id,
  ) async {


    await _apiClient.deleteAuth(
      'roles/$id/',
    );


  }


}