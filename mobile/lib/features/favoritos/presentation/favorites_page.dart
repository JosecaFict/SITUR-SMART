import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../marketplace/models/marketplace_models.dart';
import '../../marketplace/presentation/widgets/marketplace_widgets.dart';
import '../../marketplace/presentation/widgets/result_card.dart';
import '../data/favorites_store.dart';

/// Productos que el turista guardó.
class FavoritesPage extends StatefulWidget {
  const FavoritesPage({super.key, this.store});

  final FavoritesStore? store;

  @override
  State<FavoritesPage> createState() => _FavoritesPageState();
}

class _FavoritesPageState extends State<FavoritesPage> {
  late final FavoritesStore _store = widget.store ?? FavoritesStore.instance;

  List<Product> _products = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = _products.isEmpty;
      _error = null;
    });
    try {
      final products = await _store.refresh();
      if (!mounted) return;
      setState(() {
        _products = products;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = error is ApiException ? error.message : 'No se pudieron cargar tus favoritos.';
      });
    }
  }

  void _open(MarketplaceCard card) {
    if (card.hospedajeId != null) {
      context.push('/hospedaje/${card.hospedajeId}');
    } else {
      context.push('/producto/${card.id}');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppTheme.accentDark,
        foregroundColor: Colors.white,
        title: const Text('Mis favoritos', style: TextStyle(fontWeight: FontWeight.bold)),
      ),
      body: _body(),
    );
  }

  Widget _body() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return ErrorRetry(message: _error!, onRetry: _load);

    // Lo que se desmarca aquí mismo desaparece de la lista al instante.
    return ListenableBuilder(
      listenable: _store,
      builder: (context, _) {
        final visible = _products.where((product) => _store.contains(product.id)).toList();
        if (visible.isEmpty) {
          return RefreshIndicator(
            onRefresh: _load,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              children: const [
                SizedBox(height: 120),
                EmptyState(
                  icon: Icons.favorite_border,
                  title: 'Todavía no guardaste nada',
                  message: 'Toca el corazón de un hotel, tour o restaurante para encontrarlo aquí.',
                ),
              ],
            ),
          );
        }
        return RefreshIndicator(
          onRefresh: _load,
          child: ListView.separated(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
            itemCount: visible.length,
            separatorBuilder: (_, _) => const SizedBox(height: 14),
            itemBuilder: (context, index) {
              final card = MarketplaceCard.fromProduct(visible[index]);
              return ResultCard(card: card, onTap: () => _open(card));
            },
          ),
        );
      },
    );
  }
}
