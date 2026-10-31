import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../data/reviews_service.dart';

class ProductReviews extends StatefulWidget {
  const ProductReviews({super.key, required this.productId, this.service});

  final int productId;
  final ReviewsService? service;

  @override
  State<ProductReviews> createState() => _ProductReviewsState();
}

class _ProductReviewsState extends State<ProductReviews> {
  late final ReviewsService _service = widget.service ?? ReviewsService();
  final _comment = TextEditingController();
  ReviewsPage? _page;
  ProductReview? _own;
  bool _loading = true;
  bool _hasSession = false;
  bool _saving = false;
  bool _editing = false;
  int _rating = 0;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _comment.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final page = await _service.list(widget.productId);
      final hasSession = await _service.hasSession();
      ProductReview? own;
      if (hasSession) own = await _service.own(widget.productId);
      if (!mounted) return;
      setState(() {
        _page = page;
        _hasSession = hasSession;
        _own = own;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = error is ApiException
            ? error.message
            : 'No se pudieron cargar las reseñas.';
      });
    }
  }

  void _startEdit() {
    final own = _own;
    if (own == null) return;
    setState(() {
      _editing = true;
      _rating = own.rating;
      _comment.text = own.comment;
      _error = null;
    });
  }

  void _cancelEdit() => setState(() {
    _editing = false;
    _rating = 0;
    _comment.clear();
    _error = null;
  });

  Future<void> _save() async {
    final comment = _comment.text.trim();
    if (_rating < 1 || _rating > 5) {
      setState(
        () => _error = 'Selecciona una calificación de 1 a 5 estrellas.',
      );
      return;
    }
    if (comment.isEmpty) {
      setState(() => _error = 'Escribe un comentario sobre tu experiencia.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final saved = _own == null
          ? await _service.create(widget.productId, _rating, comment)
          : await _service.update(_own!.id, _rating, comment);
      if (!mounted) return;
      setState(() {
        _own = saved;
        _editing = false;
        _saving = false;
      });
      _rating = 0;
      _comment.clear();
      await _reloadList();
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = error is ApiException
            ? error.message
            : 'No se pudo guardar tu reseña.';
      });
    }
  }

  Future<void> _reloadList() async {
    try {
      final page = await _service.list(widget.productId);
      if (mounted) setState(() => _page = page);
    } catch (_) {}
  }

  Future<void> _delete() async {
    final own = _own;
    if (own == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Eliminar reseña'),
        content: const Text(
          '¿Quieres eliminar definitivamente tu calificación y comentario?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Eliminar'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _saving = true);
    try {
      await _service.delete(own.id);
      if (!mounted) return;
      setState(() {
        _own = null;
        _saving = false;
      });
      await _reloadList();
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = error is ApiException
            ? error.message
            : 'No se pudo eliminar tu reseña.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final page = _page;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Divider(height: 48),
        Text(
          'Calificaciones y reseñas',
          style: Theme.of(context).textTheme.titleLarge
              ?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 12),
        if (_loading)
          const Center(
            child: Padding(
              padding: EdgeInsets.all(20),
              child: CircularProgressIndicator(),
            ),
          )
        else if (page != null) ...[
          _Summary(page: page),
          const SizedBox(height: 16),
          if (page.items.isEmpty)
            const Text(
              'Aún no hay reseñas. Sé la primera persona en compartir su experiencia.',
              style: TextStyle(color: AppTheme.textSecondary),
            )
          else
            ...page.items.map((review) => _ReviewCard(review: review)),
          const SizedBox(height: 12),
          _editor(),
        ],
        if (_error != null) ...[
          const SizedBox(height: 10),
          Text(_error!, style: const TextStyle(color: AppTheme.errorColor)),
          if (page == null)
            TextButton(onPressed: _load, child: const Text('Reintentar')),
        ],
      ],
    );
  }

  Widget _editor() {
    if (!_hasSession) {
      return const Text(
        'Inicia sesión para publicar tu reseña.',
        style: TextStyle(color: AppTheme.textSecondary),
      );
    }
    if (_own != null && !_editing) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Tu reseña',
                style: TextStyle(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 8),
              _Stars(value: _own!.rating),
              const SizedBox(height: 8),
              Text(_own!.comment),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: [
                  TextButton.icon(
                    onPressed: _saving ? null : _startEdit,
                    icon: const Icon(Icons.edit_outlined),
                    label: const Text('Editar'),
                  ),
                  TextButton.icon(
                    onPressed: _saving ? null : _delete,
                    icon: const Icon(Icons.delete_outline),
                    label: const Text('Eliminar'),
                  ),
                ],
              ),
            ],
          ),
        ),
      );
    }
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              _editing ? 'Editar tu reseña' : 'Escribir una reseña',
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            _Stars(
              value: _rating,
              onChanged: (value) => setState(() => _rating = value),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _comment,
              enabled: !_saving,
              minLines: 3,
              maxLines: 6,
              maxLength: 1000,
              decoration: const InputDecoration(
                labelText: 'Tu comentario',
                hintText: 'Cuéntanos cómo fue tu experiencia',
              ),
            ),
            Row(
              children: [
                if (_editing)
                  TextButton(
                    onPressed: _saving ? null : _cancelEdit,
                    child: const Text('Cancelar'),
                  ),
                const Spacer(),
                FilledButton(
                  onPressed: _saving ? null : _save,
                  child: Text(_saving ? 'Guardando…' : 'Publicar'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Summary extends StatelessWidget {
  const _Summary({required this.page});
  final ReviewsPage page;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Text(
        page.average?.toStringAsFixed(1) ?? '—',
        style: const TextStyle(
          fontSize: 32,
          fontWeight: FontWeight.w900,
          color: AppTheme.accentDark,
        ),
      ),
      const SizedBox(width: 10),
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _Stars(value: page.average?.round() ?? 0),
          Text(
            '${page.count} ${page.count == 1 ? 'reseña' : 'reseñas'}',
            style: const TextStyle(color: AppTheme.textSecondary),
          ),
        ],
      ),
    ],
  );
}

class _ReviewCard extends StatelessWidget {
  const _ReviewCard({required this.review});
  final ProductReview review;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 10),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                review.author,
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ),
            Text(
              DateFormat('dd/MM/yyyy').format(review.createdAt),
              style: const TextStyle(
                fontSize: 12,
                color: AppTheme.textSecondary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        _Stars(value: review.rating, size: 18),
        const SizedBox(height: 6),
        Text(review.comment, style: const TextStyle(height: 1.4)),
      ],
    ),
  );
}

class _Stars extends StatelessWidget {
  const _Stars({required this.value, this.onChanged, this.size = 22});
  final int value;
  final ValueChanged<int>? onChanged;
  final double size;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      for (var star = 1; star <= 5; star++)
        IconButton(
          constraints: BoxConstraints.tightFor(
            width: size + 6,
            height: size + 6,
          ),
          padding: EdgeInsets.zero,
          tooltip: '$star ${star == 1 ? 'estrella' : 'estrellas'}',
          onPressed: onChanged == null ? null : () => onChanged!(star),
          icon: Icon(
            star <= value ? Icons.star : Icons.star_border,
            size: size,
            color: Colors.amber.shade700,
          ),
        ),
    ],
  );
}
