class Role {


  final int id;


  final int? tenantId;


  final String codigo;


  final String nombre;


  final String ambito;


  final bool esSistema;


  final List<String> permisos;



  const Role({

    required this.id,

    this.tenantId,

    required this.codigo,

    required this.nombre,

    required this.ambito,

    required this.esSistema,

    required this.permisos,

  });





  factory Role.fromJson(
    Map<String, dynamic> json,
  ) {


    return Role(

      id:
          json['id'] ?? 0,


      tenantId:
          json['tenant_id'],


      // Backend usa "code"
      codigo:
          json['code'] ?? '',


      // Backend usa "name"
      nombre:
          json['name'] ?? '',


      // Backend usa "scope"
      ambito:
          json['scope'] ?? '',


      // Backend usa "is_system"
      esSistema:
          json['is_system'] ?? false,


      // Backend usa "permissions"
      permisos:
          json['permissions'] != null
          ? List<String>.from(
              json['permissions'],
            )
          : [],


    );


  }



}