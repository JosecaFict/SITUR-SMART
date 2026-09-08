import '../../../core/network/api_client.dart';

import '../models/bitacora.dart';



/// Servicio encargado de consultar
/// la bitácora real del sistema.
class BitacoraService {


  final ApiClient _apiClient =
      ApiClient();



  /// Obtiene los registros de auditoría.
  ///
  /// Endpoint backend:
  /// GET /api/v1/audit/logs/
  Future<List<Bitacora>> getBitacora() async {


    final token =
        await _apiClient.getAccessToken() ?? '';



    final response =
        await _apiClient.getList(
          'audit/logs/',
          token,
        );



    return response
        .map(
          (json) =>
              Bitacora.fromJson(
                json,
              ),
        )
        .toList();

  }





  /// Obtiene un registro específico.
  ///
  /// Endpoint:
  /// GET /api/v1/audit/logs/{id}/
  Future<Bitacora> getRegistro(
    int id,
  ) async {


    final token =
        await _apiClient.getAccessToken() ?? '';



    final response =
        await _apiClient.getMap(
          'audit/logs/$id/',
          token,
        );



    return Bitacora.fromJson(
      response,
    );

  }


}