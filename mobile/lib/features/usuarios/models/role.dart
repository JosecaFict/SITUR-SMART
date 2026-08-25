class RoleModel {

  final int id;
  final String codigo;
  final String nombre;


  RoleModel({

    required this.id,

    required this.codigo,

    required this.nombre,

  });



  factory RoleModel.fromJson(
    Map<String, dynamic> json,
  ) {

    return RoleModel(

      id: json['id'],

      codigo: json['code'] ?? '',

      nombre: json['name'] ?? '',

    );

  }

}