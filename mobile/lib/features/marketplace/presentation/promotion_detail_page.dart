import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import 'widgets/marketplace_widgets.dart';

/// Detalle público de una promoción. Se abre al tocar el push de una oferta,
/// así que funciona con o sin sesión iniciada.
class PromotionDetailPage extends StatefulWidget {
  const PromotionDetailPage({super.key, required this.promotionId});

  final int promotionId;

  @override
  State<PromotionDetailPage> createState() => _PromotionDetailPageState();
}

class _PromotionDetailPageState extends State<PromotionDetailPage> {
  final ApiClient _api = ApiClient();

  Map<String, dynamic>? _data;
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
      final data = await _api.getPublic(
        'marketplace/promociones/${widget.promotionId}/',
      );
      if (!mounted) return;
      setState(() {
        _data = data as Map<String, dynamic>;
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

  String _percentage(Object? value) {
    final number = double.tryParse('${value ?? ''}');
    if (number == null) return '';
    return number == number.roundToDouble()
        ? number.toStringAsFixed(0)
        : number.toString();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(
        appBar: AppBar(),
        body: const Center(child: CircularProgressIndicator()),
      );
    }
    if (_notFound) {
      return Scaffold(
        appBar: AppBar(),
        body: const EmptyState(
          icon: Icons.local_offer_outlined,
          title: 'Esta oferta ya no está disponible',
          message: 'Puede que haya vencido o que la empresa la haya retirado.',
        ),
      );
    }
    final data = _data;
    if (_error != null || data == null) {
      return Scaffold(
        appBar: AppBar(),
        body: ErrorRetry(
          message: _error ?? 'No se pudo cargar la oferta.',
          onRetry: _load,
        ),
      );
    }

    final symbol = data['moneda_simbolo']?.toString() ?? '';
    final original = data['precio_original']?.toString();
    final finalPrice = data['precio_final']?.toString();
    final description = data['descripcion']?.toString() ?? '';
    final end = DateTime.tryParse('${data['fin'] ?? ''}')?.toLocal();
    final productId = int.tryParse('${data['producto_id'] ?? ''}');
    final components = (data['componentes'] as List<dynamic>? ?? [])
        .whereType<Map<String, dynamic>>()
        .toList();

    return Scaffold(
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            pinned: true,
            expandedHeight: 220,
            backgroundColor: AppTheme.accentDark,
            foregroundColor: Colors.white,
            flexibleSpace: FlexibleSpaceBar(
              background: ProductImage(
                url: data['imagen_url']?.toString(),
                icon: Icons.local_offer_outlined,
              ),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
            sliver: SliverList.list(
              children: [
                Align(
                  alignment: Alignment.centerLeft,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: AppTheme.errorColor,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      '-${_percentage(data['porcentaje_descuento'])}% OFERTA',
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  data['nombre']?.toString() ?? 'Oferta',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                    color: AppTheme.titleColor,
                  ),
                ),
                const SizedBox(height: 8),
                InfoLine(
                  icon: Icons.business_outlined,
                  text: 'Ofrecido por ${data['empresa'] ?? ''}',
                ),
                if (end != null)
                  InfoLine(
                    icon: Icons.schedule,
                    text:
                        'Válida hasta el ${DateFormat("d 'de' MMMM yyyy", 'es').format(end)}',
                  ),
                if (description.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  Text(
                    description,
                    style: const TextStyle(
                      height: 1.5,
                      color: AppTheme.labelColor,
                    ),
                  ),
                ],
                if (finalPrice != null) ...[
                  const SizedBox(height: 20),
                  PriceBox(
                    label: 'Precio con descuento',
                    price: '$symbol $finalPrice',
                    note: original == null ? null : 'Antes $symbol $original',
                  ),
                ],
                if (components.isNotEmpty) ...[
                  const SizedBox(height: 20),
                  const Text(
                    'Incluye',
                    style: TextStyle(
                      fontWeight: FontWeight.w700,
                      color: AppTheme.titleColor,
                    ),
                  ),
                  for (final item in components)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: const Icon(
                        Icons.check_circle_outline,
                        color: AppTheme.accentDark,
                      ),
                      title: Text(item['nombre']?.toString() ?? 'Servicio'),
                      trailing: _componentRoute(item) == null
                          ? null
                          : const Icon(Icons.chevron_right),
                      onTap: _componentRoute(item) == null
                          ? null
                          : () => context.push(_componentRoute(item)!),
                    ),
                ],
                if (productId != null) ...[
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: () => context.push('/producto/$productId'),
                    icon: const Icon(Icons.travel_explore),
                    label: const Text('Ver servicio'),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// Las habitaciones viven dentro de su hotel: no tienen ficha propia aquí.
  String? _componentRoute(Map<String, dynamic> item) {
    final id = int.tryParse('${item['producto_id'] ?? ''}');
    if (id == null || item['tipo_codigo'] == 'HABITACION') return null;
    return '/producto/$id';
  }
}
