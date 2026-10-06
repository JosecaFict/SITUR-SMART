import 'package:flutter_test/flutter_test.dart';

import 'package:mobile/core/network/api_client.dart';
import 'package:mobile/features/favoritos/data/favorites_store.dart';
import 'package:mobile/features/marketplace/models/marketplace_models.dart';

class _FakeFavoritesService extends FavoritesService {
  final Set<int> remote = {7};
  bool fail = false;

  @override
  Future<List<Product>> list() async => [
        for (final id in remote)
          Product.fromJson({'id': id, 'tipo_codigo': 'TOUR', 'nombre': 'Tour $id', 'moneda_simbolo': 'Bs'}),
      ];

  @override
  Future<void> add(int productId) async {
    if (fail) throw const ApiException('Sin conexión');
    remote.add(productId);
  }

  @override
  Future<void> remove(int productId) async {
    if (fail) throw const ApiException('Sin conexión');
    remote.remove(productId);
  }
}

void main() {
  test('carga las marcas del backend una sola vez', () async {
    final store = FavoritesStore(service: _FakeFavoritesService());
    await store.ensureLoaded();
    expect(store.contains(7), isTrue);
    expect(store.contains(8), isFalse);
  });

  test('marcar y desmarcar avisa a quien escucha', () async {
    final service = _FakeFavoritesService();
    final store = FavoritesStore(service: service);
    var notifications = 0;
    store.addListener(() => notifications++);

    await store.toggle(8);
    expect(store.contains(8), isTrue);
    expect(service.remote, contains(8));

    await store.toggle(8);
    expect(store.contains(8), isFalse);
    expect(service.remote, isNot(contains(8)));
    expect(notifications, greaterThanOrEqualTo(2));
  });

  test('si el backend falla, la marca vuelve atrás', () async {
    final service = _FakeFavoritesService()..fail = true;
    final store = FavoritesStore(service: service);

    await expectLater(store.toggle(8), throwsA(isA<ApiException>()));
    expect(store.contains(8), isFalse);
  });

  test('al cerrar sesión se olvidan las marcas', () async {
    final store = FavoritesStore(service: _FakeFavoritesService());
    await store.ensureLoaded();
    store.clear();
    expect(store.contains(7), isFalse);
  });
}
