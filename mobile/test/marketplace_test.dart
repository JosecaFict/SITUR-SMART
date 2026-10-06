import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:mobile/features/asistente/data/assistant_service.dart';
import 'package:mobile/features/marketplace/data/marketplace_service.dart';
import 'package:mobile/features/marketplace/models/marketplace_models.dart';
import 'package:mobile/features/marketplace/presentation/explore_page.dart';

Map<String, dynamic> _hotelProduct() => {
      'id': 10,
      'tipo_codigo': 'HOTEL',
      'tipo': 'Hotel',
      'nombre': 'Los Tajibos',
      'ciudad': 'Santa Cruz de la Sierra',
      'pais': 'Bolivia',
      'empresa': 'Hotel Los Tajibos S.A.',
      'moneda_simbolo': 'Bs',
      'precio_base': '0.00',
      'precio_desde': '850.00',
      'capacidad_maxima': 9999,
      'localidad': 'Equipetrol',
      'imagen_url': null,
      'hospedaje_id': 3,
      'establecimiento': null,
    };

Map<String, dynamic> _tourProduct() => {
      'id': 20,
      'tipo_codigo': 'TOUR',
      'tipo': 'Tour',
      'nombre': 'Salar de Uyuni 3 días',
      'ciudad': 'Uyuni',
      'pais': 'Bolivia',
      'empresa': 'Red Planet',
      'moneda_simbolo': 'Bs',
      'precio_base': '1200.00',
      'precio_desde': null,
      'capacidad_maxima': 6,
      'descripcion': '',
      'hospedaje_id': null,
    };

class _FakeMarketplaceService extends MarketplaceService {
  final List<MarketplaceFilters> searches = [];

  @override
  Future<List<ProductType>> productTypes() async => const [
        ProductType(id: 1, codigo: 'HOTEL', nombre: 'Hotel'),
        ProductType(id: 2, codigo: 'HABITACION', nombre: 'Habitación'),
        ProductType(id: 3, codigo: 'TOUR', nombre: 'Tour'),
      ];

  @override
  Future<List<City>> cities() async => const [City(id: 1, nombre: 'Uyuni', paisId: 1)];

  @override
  Future<PageResult<MarketplaceCard>> search(MarketplaceFilters filters, {int page = 1}) async {
    searches.add(filters);
    final items = filters.tipo == 'TOUR'
        ? [MarketplaceCard.fromProduct(Product.fromJson(_tourProduct()))]
        : [
            MarketplaceCard.fromProduct(Product.fromJson(_hotelProduct())),
            MarketplaceCard.fromProduct(Product.fromJson(_tourProduct())),
          ];
    return PageResult(count: items.length, items: items, hasNext: false);
  }
}

void main() {
  group('MarketplaceCard', () {
    test('un hotel muestra el precio desde de sus habitaciones y abre su hospedaje', () {
      final card = MarketplaceCard.fromProduct(Product.fromJson(_hotelProduct()));
      expect(card.precioEtiqueta, 'Habitaciones desde');
      expect(card.precio, 'Bs 850.00');
      expect(card.capacidad, isNull);
      expect(card.hospedajeId, 3);
      expect(card.ubicacion, 'Equipetrol, Santa Cruz de la Sierra');
    });

    test('un tour muestra su precio base y abre el detalle de producto', () {
      final card = MarketplaceCard.fromProduct(Product.fromJson(_tourProduct()));
      expect(card.precioEtiqueta, 'Desde');
      expect(card.precio, 'Bs 1200.00');
      expect(card.capacidad, 6);
      expect(card.esHospedaje, isFalse);
      expect(card.descripcion, isNull, reason: 'el texto vacío se trata como ausente');
    });

    test('un establecimiento trae estrellas y coordenadas', () {
      final lodging = Lodging.fromJson({
        'id': 3,
        'producto_id': 10,
        'tipo_hospedaje': 'Hotel',
        'nombre': 'Los Tajibos',
        'ciudad': 'Santa Cruz de la Sierra',
        'pais': 'Bolivia',
        'empresa': 'Los Tajibos',
        'moneda_simbolo': 'Bs',
        'latitud': '-17.765400',
        'longitud': '-63.196200',
        'categoria_estrellas': 5,
        'hora_check_in': '14:00:00',
        'servicios': ['Wi-Fi', 'Piscina'],
        'precio_desde': null,
        'total_habitaciones': 0,
      });
      expect(lodging.tieneUbicacion, isTrue);
      expect(lodging.latitud, closeTo(-17.7654, 1e-6));
      expect(shortTime(lodging.horaCheckIn), '14:00');
      final card = MarketplaceCard.fromLodging(lodging);
      expect(card.estrellas, 5);
      expect(card.productoId, 10, reason: 'el favorito de un hotel es su producto');
      expect(card.precio, isNull);
    });
  });

  test('las categorías ocultan Habitación y llaman Hospedajes al hotel', () {
    final types = visibleTypes(const [
      ProductType(id: 1, codigo: 'HOTEL', nombre: 'Hotel'),
      ProductType(id: 2, codigo: 'HABITACION', nombre: 'Habitación'),
      ProductType(id: 3, codigo: 'TOUR', nombre: 'Tour'),
    ]);
    expect(types.map((type) => type.nombre), ['Hospedajes', 'Tour']);
  });

  test('los filtros cuentan solo los del panel', () {
    const filters = MarketplaceFilters(buscar: 'salar', tipo: 'TOUR');
    expect(filters.activeCount, 0);
    final withCity = filters.copyWith(ciudadId: () => 4, orden: 'precio_asc');
    expect(withCity.activeCount, 2);
    expect(withCity.copyWith(ciudadId: () => null).ciudadId, isNull);
    expect(withCity.toQuery(page: 2, pageSize: 12)['ciudad'], 4);
  });

  test('el texto del asistente pierde el Markdown', () {
    expect(
      AssistantService.plainText('## Opciones\n- **Los Tajibos** en Santa Cruz\n* Otro'),
      'Opciones\n• Los Tajibos en Santa Cruz\n• Otro',
    );
  });

  testWidgets('Explorar lista resultados y filtra por categoría', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final service = _FakeMarketplaceService();
    await tester.pumpWidget(MaterialApp(home: ExplorePage(service: service)));
    await tester.pumpAndSettle();

    expect(find.text('2 resultados'), findsOneWidget);
    expect(find.text('Los Tajibos'), findsOneWidget);
    expect(find.text('Hospedajes'), findsOneWidget);
    expect(find.text('Habitación'), findsNothing);

    await tester.tap(find.widgetWithText(ChoiceChip, 'Tour'));
    await tester.pumpAndSettle();

    expect(service.searches.last.tipo, 'TOUR');
    expect(find.text('1 resultado'), findsOneWidget);
    expect(find.text('Los Tajibos'), findsNothing);
  });
}
