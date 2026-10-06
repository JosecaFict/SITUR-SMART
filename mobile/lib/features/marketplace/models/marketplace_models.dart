/// Modelos del marketplace público (marketplace/*, catalogos/*).
///
/// Los nombres siguen a la API en español. Los precios llegan como texto
/// ("450.00") desde los DecimalField de Django y así se muestran, sin pasar
/// por double, para no perder ni agregar decimales.

int? _intOrNull(Object? value) {
  if (value == null) return null;
  if (value is int) return value;
  return int.tryParse(value.toString());
}

String? _textOrNull(Object? value) {
  if (value == null) return null;
  final text = value.toString().trim();
  return text.isEmpty ? null : text;
}

double? _doubleOrNull(Object? value) {
  if (value == null) return null;
  if (value is num) return value.toDouble();
  return double.tryParse(value.toString());
}

/// "Bs 450.00" o null si no hay precio.
String? formatPrice(String symbol, String? amount) =>
    amount == null ? null : '$symbol $amount';

/// "14:00:00" → "14:00".
String? shortTime(String? time) {
  if (time == null || time.length < 5) return time;
  return time.substring(0, 5);
}

/// Página de resultados de la paginación de DRF.
class PageResult<T> {
  const PageResult({required this.count, required this.items, required this.hasNext});

  final int count;
  final List<T> items;
  final bool hasNext;

  factory PageResult.fromJson(
    Map<String, dynamic> json,
    T Function(Map<String, dynamic>) parse,
  ) {
    final results = (json['results'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(parse)
        .toList();
    return PageResult(
      count: _intOrNull(json['count']) ?? results.length,
      items: results,
      hasNext: json['next'] != null,
    );
  }
}

class City {
  const City({required this.id, required this.nombre, required this.paisId});

  final int id;
  final String nombre;
  final int? paisId;

  factory City.fromJson(Map<String, dynamic> json) => City(
        id: _intOrNull(json['id']) ?? 0,
        nombre: json['nombre']?.toString() ?? '',
        paisId: _intOrNull(json['pais_id']),
      );
}

class ProductType {
  const ProductType({required this.id, required this.codigo, required this.nombre});

  final int id;
  final String codigo;
  final String nombre;

  factory ProductType.fromJson(Map<String, dynamic> json) => ProductType(
        id: _intOrNull(json['id']) ?? 0,
        codigo: json['codigo']?.toString() ?? '',
        nombre: json['nombre']?.toString() ?? '',
      );
}

/// Categorías que se ofrecen al turista, igual que en la web: la habitación no
/// se oferta sola (se llega a ella desde su hospedaje) y HOTEL se muestra como
/// "Hospedajes".
List<ProductType> visibleTypes(List<ProductType> types) => [
      for (final type in types)
        if (type.codigo != 'HABITACION')
          type.codigo == 'HOTEL'
              ? ProductType(id: type.id, codigo: type.codigo, nombre: 'Hospedajes')
              : type,
    ];

/// Tarjeta del listado de Explorar. Productos y hospedajes llegan con formas
/// distintas y se normalizan aquí para que la lista sea una sola.
class MarketplaceCard {
  const MarketplaceCard({
    required this.id,
    required this.tipo,
    required this.nombre,
    required this.ciudad,
    required this.empresa,
    this.descripcion,
    this.localidad,
    this.imagenUrl,
    this.precioEtiqueta = 'Desde',
    this.precio,
    this.capacidad,
    this.establecimiento,
    this.hospedajeId,
    this.estrellas,
  });

  final int id;
  final String tipo;
  final String nombre;
  final String ciudad;
  final String empresa;
  final String? descripcion;
  final String? localidad;
  final String? imagenUrl;
  final String precioEtiqueta;
  final String? precio;
  final int? capacidad;
  final String? establecimiento;

  /// Si no es nulo, la tarjeta abre ese hospedaje (id de establecimiento, no
  /// de producto). Si es nulo, abre el detalle del producto.
  final int? hospedajeId;
  final int? estrellas;

  bool get esHospedaje => hospedajeId != null;

  String get ubicacion => localidad == null ? ciudad : '$localidad, $ciudad';

  /// Producto de marketplace/productos/.
  factory MarketplaceCard.fromProduct(Product product) {
    // Un hotel muestra el "desde" de sus habitaciones: su precio_base es 0 y no
    // significa nada para el turista. Una habitación cobra su precio por noche.
    var etiqueta = 'Desde';
    var precio = formatPrice(product.monedaSimbolo, product.precioBase);
    if (product.esHotel) {
      etiqueta = 'Habitaciones desde';
      precio = formatPrice(product.monedaSimbolo, product.precioDesde);
    } else if (product.esHabitacion) {
      etiqueta = 'Por noche';
    }
    return MarketplaceCard(
      id: product.id,
      tipo: product.tipo,
      nombre: product.nombre,
      ciudad: product.ciudad,
      empresa: product.empresa,
      descripcion: product.descripcion,
      localidad: product.localidad,
      imagenUrl: product.imagenUrl,
      precioEtiqueta: etiqueta,
      precio: precio,
      capacidad: product.esHotel ? null : product.capacidadMaxima,
      establecimiento: product.establecimiento,
      hospedajeId: product.hospedajeId,
    );
  }

  /// Establecimiento de marketplace/hospedajes/.
  factory MarketplaceCard.fromLodging(Lodging lodging) => MarketplaceCard(
        id: lodging.id,
        tipo: lodging.tipoHospedaje,
        nombre: lodging.nombre,
        ciudad: lodging.ciudad,
        empresa: lodging.empresa,
        descripcion: lodging.descripcion,
        localidad: lodging.localidad,
        imagenUrl: lodging.imagenUrl,
        precioEtiqueta: 'Habitaciones desde',
        precio: formatPrice(lodging.monedaSimbolo, lodging.precioDesde),
        hospedajeId: lodging.id,
        estrellas: lodging.estrellas,
      );
}

class Product {
  const Product({
    required this.id,
    required this.tipoCodigo,
    required this.tipo,
    required this.nombre,
    required this.ciudad,
    required this.pais,
    required this.empresa,
    required this.monedaSimbolo,
    required this.precioBase,
    required this.capacidadMaxima,
    this.descripcion,
    this.localidad,
    this.imagenUrl,
    this.precioDesde,
    this.hospedajeId,
    this.establecimiento,
  });

  final int id;
  final String tipoCodigo;
  final String tipo;
  final String nombre;
  final String ciudad;
  final String pais;
  final String empresa;
  final String monedaSimbolo;
  final String? precioBase;
  final int? capacidadMaxima;
  final String? descripcion;
  final String? localidad;
  final String? imagenUrl;
  final String? precioDesde;
  final int? hospedajeId;
  final String? establecimiento;

  bool get esHotel => tipoCodigo == 'HOTEL';
  bool get esHabitacion => tipoCodigo == 'HABITACION';

  factory Product.fromJson(Map<String, dynamic> json) => Product(
        id: _intOrNull(json['id']) ?? 0,
        tipoCodigo: json['tipo_codigo']?.toString() ?? '',
        tipo: json['tipo']?.toString() ?? '',
        nombre: json['nombre']?.toString() ?? '',
        ciudad: json['ciudad']?.toString() ?? '',
        pais: json['pais']?.toString() ?? '',
        empresa: json['empresa']?.toString() ?? '',
        monedaSimbolo: json['moneda_simbolo']?.toString() ?? '',
        precioBase: _textOrNull(json['precio_base']),
        capacidadMaxima: _intOrNull(json['capacidad_maxima']),
        descripcion: _textOrNull(json['descripcion']),
        localidad: _textOrNull(json['localidad']),
        imagenUrl: _textOrNull(json['imagen_url']),
        precioDesde: _textOrNull(json['precio_desde']),
        hospedajeId: _intOrNull(json['hospedaje_id']),
        establecimiento: _textOrNull(json['establecimiento']),
      );
}

class Lodging {
  const Lodging({
    required this.id,
    required this.tipoHospedaje,
    required this.nombre,
    required this.ciudad,
    required this.pais,
    required this.empresa,
    required this.monedaSimbolo,
    this.descripcion,
    this.localidad,
    this.imagenUrl,
    this.direccion,
    this.latitud,
    this.longitud,
    this.estrellas,
    this.horaCheckIn,
    this.horaCheckOut,
    this.servicios = const [],
    this.precioDesde,
    this.totalHabitaciones = 0,
  });

  final int id;
  final String tipoHospedaje;
  final String nombre;
  final String ciudad;
  final String pais;
  final String empresa;
  final String monedaSimbolo;
  final String? descripcion;
  final String? localidad;
  final String? imagenUrl;
  final String? direccion;
  final double? latitud;
  final double? longitud;
  final int? estrellas;
  final String? horaCheckIn;
  final String? horaCheckOut;
  final List<String> servicios;
  final String? precioDesde;
  final int totalHabitaciones;

  bool get tieneUbicacion => latitud != null && longitud != null;

  factory Lodging.fromJson(Map<String, dynamic> json) => Lodging(
        id: _intOrNull(json['id']) ?? 0,
        tipoHospedaje: json['tipo_hospedaje']?.toString() ?? 'Hospedaje',
        nombre: json['nombre']?.toString() ?? '',
        ciudad: json['ciudad']?.toString() ?? '',
        pais: json['pais']?.toString() ?? '',
        empresa: json['empresa']?.toString() ?? '',
        monedaSimbolo: json['moneda_simbolo']?.toString() ?? '',
        descripcion: _textOrNull(json['descripcion']),
        localidad: _textOrNull(json['localidad']),
        imagenUrl: _textOrNull(json['imagen_url']),
        direccion: _textOrNull(json['direccion']),
        latitud: _doubleOrNull(json['latitud']),
        longitud: _doubleOrNull(json['longitud']),
        estrellas: _intOrNull(json['categoria_estrellas']),
        horaCheckIn: _textOrNull(json['hora_check_in']),
        horaCheckOut: _textOrNull(json['hora_check_out']),
        servicios: [
          for (final service in json['servicios'] as List<dynamic>? ?? const [])
            service.toString(),
        ],
        precioDesde: _textOrNull(json['precio_desde']),
        totalHabitaciones: _intOrNull(json['total_habitaciones']) ?? 0,
      );
}

class Room {
  const Room({
    required this.id,
    required this.nombre,
    required this.monedaSimbolo,
    required this.precioNoche,
    required this.capacidadMaxima,
    required this.capacidadAdultos,
    required this.capacidadNinos,
    required this.cantidad,
    required this.incluyeDesayuno,
    this.descripcion,
    this.tipoCama,
    this.imagenUrl,
  });

  final int id;
  final String nombre;
  final String monedaSimbolo;
  final String? precioNoche;
  final int capacidadMaxima;
  final int capacidadAdultos;
  final int capacidadNinos;
  final int cantidad;
  final bool incluyeDesayuno;
  final String? descripcion;
  final String? tipoCama;
  final String? imagenUrl;

  factory Room.fromJson(Map<String, dynamic> json) => Room(
        id: _intOrNull(json['id']) ?? 0,
        nombre: json['nombre']?.toString() ?? '',
        monedaSimbolo: json['moneda_simbolo']?.toString() ?? '',
        precioNoche: _textOrNull(json['precio_noche']),
        capacidadMaxima: _intOrNull(json['capacidad_maxima']) ?? 0,
        capacidadAdultos: _intOrNull(json['capacidad_adultos']) ?? 0,
        capacidadNinos: _intOrNull(json['capacidad_ninos']) ?? 0,
        cantidad: _intOrNull(json['cantidad_habitaciones']) ?? 0,
        incluyeDesayuno: json['incluye_desayuno'] == true,
        descripcion: _textOrNull(json['descripcion']),
        tipoCama: _textOrNull(json['tipo_cama']),
        imagenUrl: _textOrNull(json['imagen_url']),
      );
}
