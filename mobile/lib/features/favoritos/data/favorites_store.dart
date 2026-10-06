import 'package:flutter/foundation.dart';

import '../../../core/network/api_client.dart';
import '../../marketplace/models/marketplace_models.dart';

/// Favoritos del turista (me/favoritos/).
class FavoritesService {
  FavoritesService({ApiClient? apiClient}) : _api = apiClient ?? ApiClient();

  final ApiClient _api;

  Future<List<Product>> list() async {
    final data = await _api.getList('me/favoritos/', '');
    return data.whereType<Map<String, dynamic>>().map(Product.fromJson).toList();
  }

  Future<void> add(int productId) => _api.putAuth('me/favoritos/$productId/', const {});

  Future<void> remove(int productId) => _api.deleteAuth('me/favoritos/$productId/');
}

/// Qué productos marcó el turista, compartido por todas las pantallas.
///
/// El corazón de una tarjeta, el de la ficha y la pestaña Favoritos escuchan
/// este mismo estado, así que marcar en un lado se ve en los demás sin volver
/// a consultar el backend.
class FavoritesStore extends ChangeNotifier {
  FavoritesStore({FavoritesService? service}) : _service = service ?? FavoritesService();

  static final FavoritesStore instance = FavoritesStore();

  final FavoritesService _service;
  Set<int> _ids = {};
  bool _loaded = false;
  Future<void>? _loading;

  bool contains(int productId) => _ids.contains(productId);

  /// Trae la lista completa y actualiza las marcas.
  Future<List<Product>> refresh() async {
    final products = await _service.list();
    _ids = {for (final product in products) product.id};
    _loaded = true;
    notifyListeners();
    return products;
  }

  /// Carga las marcas una sola vez. Si falla, los corazones quedan vacíos
  /// pero la pantalla sigue funcionando.
  Future<void> ensureLoaded() {
    if (_loaded) return Future.value();
    return _loading ??= refresh().then<void>((_) {}).catchError((_) {}).whenComplete(() {
      _loading = null;
    });
  }

  /// Marca o desmarca al instante y revierte si el backend falla.
  Future<void> toggle(int productId) async {
    final wasFavorite = _ids.contains(productId);
    _ids = {..._ids};
    wasFavorite ? _ids.remove(productId) : _ids.add(productId);
    notifyListeners();
    try {
      if (wasFavorite) {
        await _service.remove(productId);
      } else {
        await _service.add(productId);
      }
    } catch (_) {
      _ids = {..._ids};
      wasFavorite ? _ids.add(productId) : _ids.remove(productId);
      notifyListeners();
      rethrow;
    }
  }

  /// Al cerrar sesión: las marcas son de la cuenta, no del teléfono.
  void clear() {
    _ids = {};
    _loaded = false;
    notifyListeners();
  }
}
