class Tenant {

  final int id;
  final String nombreComercial;
  final String razonSocial;
  final String estado;


  Tenant({
    required this.id,
    required this.nombreComercial,
    required this.razonSocial,
    required this.estado,
  });


  factory Tenant.fromJson(Map<String, dynamic> json) {

    return Tenant(
      id: json['id'],
      nombreComercial: json['nombre_comercial'],
      razonSocial: json['razon_social'],
      estado: json['estado'],
    );

  }
}