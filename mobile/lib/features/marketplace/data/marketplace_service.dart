import '../../../core/network/api_client.dart';
import '../models/marketplace_models.dart';

/// Filtros de Explorar. Los vacíos no viajan al backend.
class MarketplaceFilters {
  const MarketplaceFilters({
    this.buscar = '',
    this.tipo = '',
    this.ciudadId,
    this.precioMin,
    this.precioMax,
    this.orden = 'recientes',
  });

  final String buscar;

  /// Código del tipo de producto; vacío = todas las categorías.
  final String tipo;
  final int? ciudadId;
  final String? precioMin;
  final String? precioMax;

  /// recientes, precio_asc, precio_desc o nombre.
  final String orden;

  /// Cuántos filtros del panel están activos (sin contar búsqueda ni categoría).
  int get activeCount =>
      [ciudadId, precioMin, precioMax].where((value) => value != null).length +
      (orden == 'recientes' ? 0 : 1);

  MarketplaceFilters copyWith({
    String? buscar,
    String? tipo,
    int? Function()? ciudadId,
    String? Function()? precioMin,
    String? Function()? precioMax,
    String? orden,
  }) =>
      MarketplaceFilters(
        buscar: buscar ?? this.buscar,
        tipo: tipo ?? this.tipo,
        ciudadId: ciudadId != null ? ciudadId() : this.ciudadId,
        precioMin: precioMin != null ? precioMin() : this.precioMin,
        precioMax: precioMax != null ? precioMax() : this.precioMax,
        orden: orden ?? this.orden,
      );

  Map<String, Object?> toQuery({required int page, required int pageSize}) => {
        'buscar': buscar.trim(),
        'ciudad': ciudadId,
        'precio_min': precioMin,
        'precio_max': precioMax,
        'orden': orden,
        'page': page,
        'page_size': pageSize,
      };
}

/// Consultas públicas del marketplace. No necesitan sesión.
class MarketplaceService {
  MarketplaceService({ApiClient? apiClient}) : _api = apiClient ?? ApiClient();

  static const int pageSize = 12;

  final ApiClient _api;

  Future<List<ProductType>> productTypes() async =>
      _list(await _api.getPublic('catalogos/tipos-producto/'), ProductType.fromJson);

  Future<List<City>> cities() async =>
      _list(await _api.getPublic('catalogos/ciudades/'), City.fromJson);

  /// Una página de Explorar. Los hospedajes van por su propio endpoint porque
  /// solo él conoce las estrellas y el precio "desde" de cada hotel.
  Future<PageResult<MarketplaceCard>> search(MarketplaceFilters filters, {int page = 1}) async {
    final query = filters.toQuery(page: page, pageSize: pageSize);
    if (filters.tipo == 'HOTEL') {
      final data = await _api.getPublic('marketplace/hospedajes/', query: query);
      return PageResult.fromJson(
        data as Map<String, dynamic>,
        (json) => MarketplaceCard.fromLodging(Lodging.fromJson(json)),
      );
    }
    final data = await _api.getPublic(
      'marketplace/productos/',
      query: {...query, 'tipo': filters.tipo},
    );
    return PageResult.fromJson(
      data as Map<String, dynamic>,
      (json) => MarketplaceCard.fromProduct(Product.fromJson(json)),
    );
  }

  Future<Product> product(int id) async =>
      Product.fromJson(await _api.getPublic('marketplace/productos/$id/') as Map<String, dynamic>);

  Future<Lodging> lodging(int id) async =>
      Lodging.fromJson(await _api.getPublic('marketplace/hospedajes/$id/') as Map<String, dynamic>);

  /// Habitaciones publicadas del hospedaje, de la más económica a la más cara.
  Future<List<Room>> lodgingRooms(int id) async =>
      _list(await _api.getPublic('marketplace/hospedajes/$id/habitaciones/'), Room.fromJson);

  List<T> _list<T>(dynamic data, T Function(Map<String, dynamic>) parse) {
    if (data is! List) throw const ApiException('El backend no devolvió una lista válida.');
    return data.whereType<Map<String, dynamic>>().map(parse).toList();
  }
}
