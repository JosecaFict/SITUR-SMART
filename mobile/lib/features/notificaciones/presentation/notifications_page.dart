import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../marketplace/presentation/widgets/marketplace_widgets.dart';
import '../data/notifications_store.dart';

/// Bandeja de avisos: reservas confirmadas, vencidas, canceladas.
class NotificationsInboxPage extends StatefulWidget {
  const NotificationsInboxPage({super.key, this.service, this.store});

  final NotificationsService? service;
  final NotificationsStore? store;

  @override
  State<NotificationsInboxPage> createState() => _NotificationsInboxPageState();
}

class _NotificationsInboxPageState extends State<NotificationsInboxPage> {
  late final NotificationsService _service = widget.service ?? NotificationsService();
  late final NotificationsStore _store = widget.store ?? NotificationsStore.instance;
  final ScrollController _scroll = ScrollController();

  final List<AppNotification> _items = [];
  int _page = 1;
  bool _hasNext = false;
  bool _loading = true;
  bool _loadingMore = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels > _scroll.position.maxScrollExtent - 300) _loadMore();
    });
    _load();
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = _items.isEmpty;
      _error = null;
    });
    try {
      final page = await _service.list();
      if (!mounted) return;
      setState(() {
        _items
          ..clear()
          ..addAll(page.items);
        _page = 1;
        _hasNext = page.hasNext;
        _loading = false;
      });
      _store.refresh();
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = error is ApiException ? error.message : 'No se pudieron cargar tus notificaciones.';
      });
    }
  }

  Future<void> _loadMore() async {
    if (_loading || _loadingMore || !_hasNext) return;
    setState(() => _loadingMore = true);
    try {
      final page = await _service.list(page: _page + 1);
      if (!mounted) return;
      setState(() {
        _items.addAll(page.items);
        _page += 1;
        _hasNext = page.hasNext;
      });
    } catch (_) {
      // Se reintenta al volver a llegar al final.
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  Future<void> _open(int index) async {
    final item = _items[index];
    if (!item.read) {
      setState(() => _items[index] = item.copyWith(read: true));
      _store.decrement();
      _service.markRead(item.id).catchError((_) {});
    }
    if (item.bookingId != null) context.push('/reserva/${item.bookingId}');
  }

  Future<void> _markAll() async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await _service.markAllRead();
      if (!mounted) return;
      setState(() {
        for (var i = 0; i < _items.length; i++) {
          _items[i] = _items[i].copyWith(read: true);
        }
      });
      _store.clear();
    } catch (error) {
      messenger.showSnackBar(
        SnackBar(content: Text(error is ApiException ? error.message : 'No se pudo actualizar.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final anyUnread = _items.any((item) => !item.read);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notificaciones'),
        actions: [
          if (anyUnread)
            TextButton(onPressed: _markAll, child: const Text('Marcar todas')),
        ],
      ),
      body: _body(),
    );
  }

  Widget _body() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return ErrorRetry(message: _error!, onRetry: _load);
    if (_items.isEmpty) {
      return RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: const [
            SizedBox(height: 120),
            EmptyState(
              icon: Icons.notifications_none,
              title: 'No tienes notificaciones',
              message: 'Aquí te avisaremos cuando se confirme o venza una reserva.',
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        controller: _scroll,
        physics: const AlwaysScrollableScrollPhysics(),
        itemCount: _items.length + (_loadingMore ? 1 : 0),
        separatorBuilder: (_, _) => const Divider(height: 1),
        itemBuilder: (context, index) {
          if (index == _items.length) {
            return const Padding(
              padding: EdgeInsets.all(16),
              child: Center(child: CircularProgressIndicator()),
            );
          }
          return _NotificationTile(item: _items[index], onTap: () => _open(index));
        },
      ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  const _NotificationTile({required this.item, required this.onTap});

  final AppNotification item;
  final VoidCallback onTap;

  static String _when(DateTime value) {
    final now = DateTime.now();
    final difference = now.difference(value);
    if (difference.inMinutes < 1) return 'Ahora';
    if (difference.inHours < 1) return 'Hace ${difference.inMinutes} min';
    if (difference.inDays < 1 && now.day == value.day) return DateFormat('HH:mm').format(value);
    return DateFormat('dd/MM/yyyy').format(value);
  }

  @override
  Widget build(BuildContext context) {
    final (IconData icon, Color color) = switch (item.kind) {
      'RESERVA_CONFIRMADA' => (Icons.check_circle, const Color(0xFF047857)),
      'RESERVA_VENCIDA' => (Icons.timer_off_outlined, const Color(0xFFB45309)),
      'PAGO_REVISION' => (Icons.report_outlined, AppTheme.errorColor),
      _ => (Icons.info_outline, AppTheme.textSecondary),
    };
    return Material(
      color: item.read ? Colors.white : AppTheme.demoBg,
      child: ListTile(
        onTap: onTap,
        leading: CircleAvatar(
          backgroundColor: color.withValues(alpha: 0.12),
          child: Icon(icon, color: color),
        ),
        title: Text(
          item.title,
          style: TextStyle(
            fontWeight: item.read ? FontWeight.w500 : FontWeight.w800,
            color: AppTheme.titleColor,
          ),
        ),
        subtitle: Text(item.message),
        trailing: Text(_when(item.createdAt), style: const TextStyle(fontSize: 12)),
        isThreeLine: true,
      ),
    );
  }
}
