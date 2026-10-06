import 'package:flutter/material.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../favoritos/presentation/favorite_button.dart';
import '../../models/marketplace_models.dart';
import 'marketplace_widgets.dart';

/// Tarjeta de un resultado del marketplace, con el corazón de favoritos sobre
/// la foto. La comparten Explorar y Favoritos.
class ResultCard extends StatelessWidget {
  const ResultCard({super.key, required this.card, required this.onTap});

  final MarketplaceCard card;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: AppTheme.inputBorder),
      ),
      child: InkWell(
        onTap: onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            AspectRatio(
              aspectRatio: 16 / 9,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  ProductImage(
                    url: card.imagenUrl,
                    icon: card.esHospedaje ? Icons.hotel_outlined : Icons.landscape_outlined,
                  ),
                  Positioned(
                    top: 10,
                    left: 10,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        card.tipo,
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.accentDark,
                        ),
                      ),
                    ),
                  ),
                  Positioned(
                    top: 4,
                    right: 4,
                    child: FavoriteButton(productId: card.productoId, onImage: true),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    card.nombre,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.titleColor,
                    ),
                  ),
                  if (card.estrellas != null) ...[
                    const SizedBox(height: 4),
                    StarRow(count: card.estrellas!),
                  ],
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      const Icon(Icons.place_outlined, size: 16, color: AppTheme.textSecondary),
                      const SizedBox(width: 4),
                      Expanded(
                        child: Text(card.ubicacion, maxLines: 1, overflow: TextOverflow.ellipsis),
                      ),
                    ],
                  ),
                  Text(
                    card.establecimiento != null
                        ? 'En ${card.establecimiento}'
                        : card.empresa,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 13),
                  ),
                  const Divider(height: 20),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Expanded(
                        child: card.precio == null
                            ? const Text('Consultar precio')
                            : Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(card.precioEtiqueta, style: const TextStyle(fontSize: 12)),
                                  Text(
                                    card.precio!,
                                    style: const TextStyle(
                                      fontSize: 18,
                                      fontWeight: FontWeight.w800,
                                      color: AppTheme.accentDark,
                                    ),
                                  ),
                                ],
                              ),
                      ),
                      Text(
                        card.esHospedaje ? 'Ver habitaciones →' : 'Ver detalle →',
                        style: const TextStyle(
                          fontWeight: FontWeight.w700,
                          color: AppTheme.accentDark,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
