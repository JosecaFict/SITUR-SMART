class UserModel {


  final int id;

  final String email;

  final String nombres;

  final String apellidos;

  final String? telefono;

  final String estado;





  UserModel({


    required this.id,

    required this.email,

    required this.nombres,

    required this.apellidos,

    this.telefono,

    required this.estado,


  });







  factory UserModel.fromJson(

    Map<String, dynamic> json,

  ) {


    return UserModel(


      id: json['id'] ?? 0,


      email: json['email'] ?? '',


      nombres: json['nombres'] ?? '',


      apellidos: json['apellidos'] ?? '',


      telefono: json['telefono'],


      estado: json['estado'] ?? '',



    );


  }



}