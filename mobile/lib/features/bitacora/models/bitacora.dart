/// Modelo de un registro de auditoría.
///
/// Corresponde a la tabla:
/// bitacora

class Bitacora {


  final int id;

  final String? usuario;

  final String? correo;

  final String accion;

  final String entidad;

  final String? entidadId;

  final String? empresa;

  final Map<String,dynamic>? datosAnteriores;

  final Map<String,dynamic>? datosNuevos;

  final String? ip;

  final String? userAgent;

  final String? requestId;

  final DateTime fecha;



  const Bitacora({

    required this.id,

    this.usuario,

    this.correo,

    required this.accion,

    required this.entidad,

    this.entidadId,

    this.empresa,

    this.datosAnteriores,

    this.datosNuevos,

    this.ip,

    this.userAgent,

    this.requestId,

    required this.fecha,

  });



  factory Bitacora.fromJson(
      Map<String,dynamic> json
  ){

    final user =
        json['usuario'] ?? json['user'];



    return Bitacora(

      id:
          json['id'] ?? 0,


      usuario:
          user is Map
          ? user['nombre']?.toString()
          : user?.toString(),


      correo:
          user is Map
          ? user['correo']?.toString()
          : null,


      empresa:
          json['empresa']?.toString(),


      accion:
          (json['accion'] ??
           json['action'] ??
           '')
          .toString(),


      entidad:
          (json['entidad'] ??
           json['entity'] ??
           '')
          .toString(),


      entidadId:
          (
            json['entidad_id'] ??
            json['entity_id']
          )?.toString(),



      datosAnteriores:

          json['datos_anteriores'] != null

          ? Map<String,dynamic>.from(
              json['datos_anteriores']
            )

          :

          json['previous_data'] != null

          ? Map<String,dynamic>.from(
              json['previous_data']
            )

          : null,



      datosNuevos:

          json['datos_nuevos'] != null

          ? Map<String,dynamic>.from(
              json['datos_nuevos']
            )

          :

          json['new_data'] != null

          ? Map<String,dynamic>.from(
              json['new_data']
            )

          : null,



      ip:
          json['ip']?.toString(),


      userAgent:
          json['user_agent']?.toString(),


      requestId:
          json['request_id']?.toString(),



      fecha:

          DateTime.parse(

            (
              json['fecha'] ??
              json['created_at']
            ).toString()

          ),

    );

  }

}