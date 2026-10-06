import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../data/marketplace_service.dart';
import '../models/marketplace_models.dart';
import 'widgets/marketplace_widgets.dart';

/// Detalle de un tour, experiencia, atracción, restaurante o paquete.
class ProductDetailPage extends StatefulWidget {
  const ProductDetailPage({super.key, required this.productId, this.service});

  final int productId;
  final MarketplaceService? service;

  @override
  State<ProductDetailPage> createState() => _ProductDetailPageState();
}

class _ProductDetailPageState extends State<ProductDetailPage> {
  late final MarketplaceService _service = widget.service ?? MarketplaceService();

  Product? _product;
  bool _loading = true;
  bool _notFound = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
      _notFound = false;
    });
    try {
      final product = await _service.product(widget.productId);
      if (!mounted) return;
      setState(() {
        _product = product;
        _loading = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _notFound = error.statusCode == 404;
        _error = error.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'No se pudo conectar con el servidor. Revisa tu conexión.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final product = _product;
    if (_loading) {
      return Scaffold(appBar: AppBar(), body: const Center(child: CircularProgressIndicator()));
    }
    if (_notFound) {
      return Scaffold(
        appBar: AppBar(),
        body: const EmptyState(
          icon: Icons.travel_explore,
          title: 'Este producto no está disponible',
          message: 'Puede que ya no esté publicado.',
        ),
      );
    }
    if (_error != null || product == null) {
      return Scaffold(
        appBar: AppBar(),
        body: ErrorRetry(message: _error ?? 'No se pudo cargar el producto.', onRetry: _load),
      );
    }

    final location = [
      if (product.localidad != null) product.localidad!,
      product.ciudad,
      product.pais,
    ].join(', ');
    final price = formatPrice(product.monedaSimbolo, product.precioBase);

    return Scaffold(
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            pinned: true,
            expandedHeight: 240,
            backgroundColor: AppTheme.accentDark,
            foregroundColor: Colors.white,
            flexibleSpace: FlexibleSpaceBar(
              background: ProductImage(url: product.imagenUrl, icon: Icons.landscape_outlined),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
            sliver: SliverList.list(
              children: [
                Text(
                  product.tipo.toUpperCase(),
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.accentDark,
                    letterSpacing: 0.5,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  product.nombre,
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w800,
                        color: AppTheme.titleColor,
                      ),
                ),
                const SizedBox(height: 8),
                InfoLine(icon: Icons.place_outlined, text: location),
                InfoLine(icon: Icons.business_outlined, text: 'Ofrecido por ${product.empresa}'),
                if (product.capacidadMaxima != null && product.capacidadMaxima! > 0)
                  InfoLine(
                    icon: Icons.people_outline,
                    text: 'Hasta ${product.capacidadMaxima} '
                        '${product.capacidadMaxima == 1 ? 'persona' : 'personas'}',
                  ),
                if (product.descripcion != null) ...[
                  const SizedBox(height: 16),
                  Text(product.descripcion!, style: const TextStyle(height: 1.5, color: AppTheme.labelColor)),
                ],
                if (price != null) ...[
                  const SizedBox(height: 20),
                  PriceBox(label: 'Desde', price: price),
                ],
                // Un hotel o una habitación abiertos por enlace directo: su ficha
                // completa vive en la página del hospedaje.
                if (product.hospedajeId != null) ...[
                  const SizedBox(height: 20),
                  ElevatedButton.icon(
                    onPressed: () => context.pushReplacement('/hospedaje/${product.hospedajeId}'),
                    icon: const Icon(Icons.hotel_outlined),
                    label: const Text('Ver el hospedaje'),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
