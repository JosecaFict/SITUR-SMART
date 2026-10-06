import 'package:flutter/material.dart';

import '../../../core/network/api_client.dart';
import '../data/favorites_store.dart';

/// Corazón para marcar un producto como favorito.
class FavoriteButton extends StatefulWidget {
  const FavoriteButton({super.key, required this.productId, this.onImage = false, this.store});

  final int productId;

  /// Sobre una foto lleva fondo blanco para que se vea.
  final bool onImage;
  final FavoritesStore? store;

  @override
  State<FavoriteButton> createState() => _FavoriteButtonState();
}

class _FavoriteButtonState extends State<FavoriteButton> {
  late final FavoritesStore _store = widget.store ?? FavoritesStore.instance;

  @override
  void initState() {
    super.initState();
    _store.ensureLoaded();
  }

  Future<void> _toggle() async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await _store.toggle(widget.productId);
    } catch (error) {
      messenger.showSnackBar(
        SnackBar(
          content: Text(
            error is ApiException ? error.message : 'No se pudo actualizar tus favoritos.',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _store,
      builder: (context, _) {
        final favorite = _store.contains(widget.productId);
        return IconButton(
          tooltip: favorite ? 'Quitar de favoritos' : 'Guardar en favoritos',
          onPressed: _toggle,
          style: widget.onImage
              ? IconButton.styleFrom(backgroundColor: Colors.white.withValues(alpha: 0.9))
              : null,
          icon: Icon(
            favorite ? Icons.favorite : Icons.favorite_border,
            color: favorite ? const Color(0xFFE11D48) : (widget.onImage ? Colors.black87 : null),
          ),
        );
      },
    );
  }
}
