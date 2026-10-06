import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../notificaciones/presentation/notification_bell.dart';
import '../data/marketplace_service.dart';
import '../models/marketplace_models.dart';
import 'widgets/marketplace_widgets.dart';
import 'widgets/result_card.dart';

/// Marketplace del turista: búsqueda, categorías, filtros y resultados con
/// carga de más páginas al llegar al final de la lista.
class ExplorePage extends StatefulWidget {
  const ExplorePage({super.key, this.service});

  /// Inyectable para pruebas.
  final MarketplaceService? service;

  @override
  State<ExplorePage> createState() => _ExplorePageState();
}

class _ExplorePageState extends State<ExplorePage> {
  late final MarketplaceService _service = widget.service ?? MarketplaceService();
  final TextEditingController _searchController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  MarketplaceFilters _filters = const MarketplaceFilters();
  List<ProductType> _types = const [];
  List<City> _cities = const [];

  final List<MarketplaceCard> _cards = [];
  int _total = 0;
  int _page = 1;
  bool _hasNext = false;
  bool _loading = true;
  bool _loadingMore = false;
  String? _error;

  /// Cada búsqueda nueva invalida las respuestas de las anteriores: si el
  /// turista cambia de categoría rápido, una respuesta lenta no pisa la nueva.
  int _requestId = 0;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _loadCatalogs();
    _search();
  }

  @override
  void dispose() {
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _loadCatalogs() async {
    // Sin catálogos la búsqueda sigue funcionando; solo faltan chips y ciudades.
    try {
      final results = await Future.wait([_service.productTypes(), _service.cities()]);
      if (!mounted) return;
      setState(() {
        _types = visibleTypes(results[0] as List<ProductType>);
        _cities = results[1] as List<City>;
      });
    } catch (_) {}
  }

  Future<void> _search() async {
    final requestId = ++_requestId;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await _service.search(_filters);
      if (!mounted || requestId != _requestId) return;
      setState(() {
        _cards
          ..clear()
          ..addAll(result.items);
        _total = result.count;
        _page = 1;
        _hasNext = result.hasNext;
        _loading = false;
      });
      if (_scrollController.hasClients) _scrollController.jumpTo(0);
    } catch (error) {
      if (!mounted || requestId != _requestId) return;
      setState(() {
        _loading = false;
        _error = _messageFor(error);
      });
    }
  }

  Future<void> _loadMore() async {
    if (_loading || _loadingMore || !_hasNext) return;
    final requestId = _requestId;
    setState(() => _loadingMore = true);
    try {
      final result = await _service.search(_filters, page: _page + 1);
      if (!mounted || requestId != _requestId) return;
      setState(() {
        _cards.addAll(result.items);
        _page += 1;
        _hasNext = result.hasNext;
        _loadingMore = false;
      });
    } catch (error) {
      if (!mounted || requestId != _requestId) return;
      setState(() => _loadingMore = false);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(_messageFor(error))));
    }
  }

  void _onScroll() {
    final position = _scrollController.position;
    if (position.pixels > position.maxScrollExtent - 400) _loadMore();
  }

  String _messageFor(Object error) {
    if (error is ApiException) return error.message;
    return 'No se pudo conectar con el servidor. Revisa tu conexión.';
  }

  void _applyFilters(MarketplaceFilters filters) {
    setState(() => _filters = filters);
    _search();
  }

  void _submitSearch(String text) => _applyFilters(_filters.copyWith(buscar: text));

  void _open(MarketplaceCard card) {
    if (card.hospedajeId != null) {
      context.push('/hospedaje/${card.hospedajeId}');
    } else {
      context.push('/producto/${card.id}');
    }
  }

  Future<void> _openFilters() async {
    final result = await showModalBottomSheet<MarketplaceFilters>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _FiltersSheet(filters: _filters, cities: _cities),
    );
    if (result != null) _applyFilters(result);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppTheme.accentDark,
        foregroundColor: Colors.white,
        title: const Text('Explorar Bolivia', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: const [NotificationBell()],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(64),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _searchController,
                    textInputAction: TextInputAction.search,
                    onSubmitted: _submitSearch,
                    decoration: InputDecoration(
                      hintText: 'Buscar hoteles, tours, lugares…',
                      prefixIcon: const Icon(Icons.search),
                      fillColor: Colors.white,
                      contentPadding: const EdgeInsets.symmetric(vertical: 10),
                      suffixIcon: _filters.buscar.isEmpty
                          ? null
                          : IconButton(
                              tooltip: 'Limpiar búsqueda',
                              icon: const Icon(Icons.close),
                              onPressed: () {
                                _searchController.clear();
                                _submitSearch('');
                              },
                            ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Badge(
                  isLabelVisible: _filters.activeCount > 0,
                  label: Text('${_filters.activeCount}'),
                  child: IconButton.filled(
                    tooltip: 'Filtros',
                    style: IconButton.styleFrom(backgroundColor: Colors.white24),
                    onPressed: _openFilters,
                    icon: const Icon(Icons.tune, color: Colors.white),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
      body: Column(
        children: [
          _CategoryChips(
            types: _types,
            selected: _filters.tipo,
            onSelected: (code) => _applyFilters(_filters.copyWith(tipo: code)),
          ),
          Expanded(child: _results()),
        ],
      ),
    );
  }

  Widget _results() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return ErrorRetry(message: _error!, onRetry: _search);
    if (_cards.isEmpty) {
      return EmptyState(
        icon: Icons.travel_explore,
        title: 'No encontramos resultados',
        message: 'Prueba con otra categoría o quita algunos filtros.',
        action: _filters.activeCount > 0 || _filters.buscar.isNotEmpty
            ? OutlinedButton(
                onPressed: () {
                  _searchController.clear();
                  _applyFilters(MarketplaceFilters(tipo: _filters.tipo));
                },
                child: const Text('Quitar filtros'),
              )
            : null,
      );
    }
    return RefreshIndicator(
      onRefresh: _search,
      child: ListView.separated(
        controller: _scrollController,
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
        itemCount: _cards.length + 2,
        separatorBuilder: (_, _) => const SizedBox(height: 14),
        itemBuilder: (context, index) {
          if (index == 0) {
            return Text(
              '$_total ${_total == 1 ? 'resultado' : 'resultados'}',
              style: const TextStyle(fontSize: 13),
            );
          }
          if (index == _cards.length + 1) {
            return _loadingMore
                ? const Padding(
                    padding: EdgeInsets.all(12),
                    child: Center(child: CircularProgressIndicator()),
                  )
                : const SizedBox.shrink();
          }
          final card = _cards[index - 1];
          return ResultCard(card: card, onTap: () => _open(card));
        },
      ),
    );
  }
}

class _CategoryChips extends StatelessWidget {
  const _CategoryChips({required this.types, required this.selected, required this.onSelected});

  final List<ProductType> types;
  final String selected;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    final options = [const ProductType(id: 0, codigo: '', nombre: 'Todos'), ...types];
    return SizedBox(
      height: 56,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        itemCount: options.length,
        separatorBuilder: (_, _) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final type = options[index];
          return ChoiceChip(
            label: Text(type.nombre),
            selected: selected == type.codigo,
            onSelected: (_) => onSelected(type.codigo),
          );
        },
      ),
    );
  }
}

/// Panel de filtros: ciudad, rango de precio y orden.
class _FiltersSheet extends StatefulWidget {
  const _FiltersSheet({required this.filters, required this.cities});

  final MarketplaceFilters filters;
  final List<City> cities;

  @override
  State<_FiltersSheet> createState() => _FiltersSheetState();
}

class _FiltersSheetState extends State<_FiltersSheet> {
  static const _orders = {
    'recientes': 'Más recientes',
    'precio_asc': 'Precio: menor a mayor',
    'precio_desc': 'Precio: mayor a menor',
    'nombre': 'Nombre (A-Z)',
  };

  late int? _cityId = widget.filters.ciudadId;
  late String _order = widget.filters.orden;
  late final TextEditingController _min = TextEditingController(text: widget.filters.precioMin ?? '');
  late final TextEditingController _max = TextEditingController(text: widget.filters.precioMax ?? '');
  String? _priceError;

  @override
  void dispose() {
    _min.dispose();
    _max.dispose();
    super.dispose();
  }

  String? _price(TextEditingController controller) {
    final text = controller.text.trim().replaceAll(',', '.');
    return text.isEmpty ? null : text;
  }

  void _apply() {
    final min = _price(_min);
    final max = _price(_max);
    final minValue = min == null ? null : double.tryParse(min);
    final maxValue = max == null ? null : double.tryParse(max);
    if ((min != null && minValue == null) || (max != null && maxValue == null)) {
      setState(() => _priceError = 'Ingresa precios válidos.');
      return;
    }
    if (minValue != null && maxValue != null && minValue > maxValue) {
      setState(() => _priceError = 'El precio máximo debe ser mayor o igual que el mínimo.');
      return;
    }
    Navigator.pop(
      context,
      widget.filters.copyWith(
        ciudadId: () => _cityId,
        precioMin: () => min,
        precioMax: () => max,
        orden: _order,
      ),
    );
  }

  void _clear() {
    Navigator.pop(
      context,
      widget.filters.copyWith(
        ciudadId: () => null,
        precioMin: () => null,
        precioMax: () => null,
        orden: 'recientes',
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cities = [...widget.cities]..sort((a, b) => a.nombre.compareTo(b.nombre));
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, MediaQuery.viewInsetsOf(context).bottom + 20),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Filtros', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 16),
            DropdownButtonFormField<int?>(
              initialValue: cities.any((city) => city.id == _cityId) ? _cityId : null,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Ciudad'),
              items: [
                const DropdownMenuItem<int?>(value: null, child: Text('Todas las ciudades')),
                for (final city in cities)
                  DropdownMenuItem<int?>(value: city.id, child: Text(city.nombre)),
              ],
              onChanged: (value) => setState(() => _cityId = value),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _min,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: 'Precio mínimo'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: _max,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: 'Precio máximo'),
                  ),
                ),
              ],
            ),
            if (_priceError != null)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(_priceError!, style: const TextStyle(color: AppTheme.errorColor)),
              ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: _order,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Ordenar por'),
              items: [
                for (final entry in _orders.entries)
                  DropdownMenuItem(value: entry.key, child: Text(entry.value)),
              ],
              onChanged: (value) => setState(() => _order = value ?? 'recientes'),
            ),
            const SizedBox(height: 24),
            ElevatedButton(onPressed: _apply, child: const Text('Aplicar filtros')),
            const SizedBox(height: 8),
            TextButton(onPressed: _clear, child: const Text('Limpiar filtros')),
          ],
        ),
      ),
    );
  }
}
