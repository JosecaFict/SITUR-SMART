import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/network/api_client.dart';
import '../../../core/storage/token_storage.dart';
import '../../../core/theme/app_theme.dart';
import '../../marketplace/presentation/widgets/marketplace_widgets.dart';
import '../../usuarios/data/auth_service.dart';
import '../data/notifications_store.dart';
import 'communication_preferences_sheet.dart';

/// Bandeja de avisos de reservas y comunicaciones recibidas.
class NotificationsInboxPage extends StatefulWidget {
  const NotificationsInboxPage({super.key, this.service, this.store});

  final NotificationsService? service;
  final NotificationsStore? store;

  @override
  State<NotificationsInboxPage> createState() => _NotificationsInboxPageState();
}

class _NotificationsInboxPageState extends State<NotificationsInboxPage> {
  late final NotificationsService _service =
      widget.service ?? NotificationsService();
  late final NotificationsStore _store =
      widget.store ?? NotificationsStore.instance;
  final ScrollController _scroll = ScrollController();

  final List<AppNotification> _items = [];
  final Set<int> _markingRead = {};
  int _page = 1;
  bool _hasNext = false;
  bool _loading = true;
  bool _loadingMore = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels > _scroll.position.maxScrollExtent - 300) {
        _loadMore();
      }
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
        _error = error is ApiException
            ? error.message
            : 'No se pudieron cargar tus notificaciones.';
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
    if (!item.read) _markRead(item.id);
    if (item.isCommunication || item.promotionId != null) {
      final user = item.bookingId == null
          ? null
          : await TokenStorage().getUser();
      if (!mounted) return;
      final canOpenBooking = user != null && !AuthService.isStaff(user);
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        useSafeArea: true,
        builder: (sheetContext) => _CommunicationDetails(
          item: item,
          onOpenBooking: !canOpenBooking || item.bookingId == null
              ? null
              : () {
                  Navigator.of(sheetContext).pop();
                  context.push('/reserva/${item.bookingId}');
                },
          onOpenOffer: item.promotionId == null || item.expired
              ? null
              : () async {
                  if (item.expired) return;
                  const webUrl = String.fromEnvironment(
                    'WEB_URL',
                    defaultValue: 'https://situr-smart-web.vercel.app',
                  );
                  final opened = await launchUrl(
                    Uri.parse(
                      '$webUrl/marketplace/promociones/${item.promotionId}',
                    ),
                    mode: LaunchMode.externalApplication,
                  );
                  if (!opened && mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('No se pudo abrir la oferta.'),
                      ),
                    );
                  }
                },
        ),
      );
    } else if (item.bookingId != null) {
      context.push('/reserva/${item.bookingId}');
    }
  }

  Future<void> _markRead(int id) async {
    if (!_markingRead.add(id)) return;
    try {
      await _service.markRead(id);
      if (!mounted) return;
      final index = _items.indexWhere((item) => item.id == id);
      if (index < 0 || _items[index].read) return;
      setState(() => _items[index] = _items[index].copyWith(read: true));
      _store.decrement();
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No se pudo marcar como leída. Vuelve a intentarlo.'),
        ),
      );
    } finally {
      _markingRead.remove(id);
    }
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
        SnackBar(
          content: Text(
            error is ApiException ? error.message : 'No se pudo actualizar.',
          ),
        ),
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
          IconButton(
            tooltip: 'Preferencias de promociones',
            icon: const Icon(Icons.tune),
            onPressed: () => showModalBottomSheet<void>(
              context: context,
              isScrollControlled: true,
              useSafeArea: true,
              builder: (_) => const CommunicationPreferencesSheet(),
            ),
          ),
          if (anyUnread)
            TextButton(onPressed: _markAll, child: const Text('Marcar todas')),
        ],
      ),
      backgroundColor: const Color(0xFFF4F8F5),
      body: Column(
        children: [
          Container(
            width: double.infinity,
            margin: const EdgeInsets.fromLTRB(16, 12, 16, 16),
            padding: const EdgeInsets.all(22),
            decoration: BoxDecoration(
              color: const Color(0xFF104F40),
              borderRadius: BorderRadius.circular(22),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'TU BANDEJA',
                  style: TextStyle(
                    color: Color(0xFFBDE5CC),
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Siempre al tanto.',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 24,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 6),
                const Text(
                  'Tus viajes, tu equipo y nuevas experiencias, en un solo lugar.',
                  style: TextStyle(color: Color(0xFFD2E8DB), fontSize: 16),
                ),
              ],
            ),
          ),
          Expanded(child: _body()),
        ],
      ),
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
              message:
                  'Aquí recibirás comunicaciones y avisos de tus reservas.',
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
        separatorBuilder: (_, _) => const SizedBox(height: 4),
        itemBuilder: (context, index) {
          if (index == _items.length) {
            return const Padding(
              padding: EdgeInsets.all(16),
              child: Center(child: CircularProgressIndicator()),
            );
          }
          return _NotificationTile(
            item: _items[index],
            onTap: () => _open(index),
          );
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
    if (difference.inDays < 1 && now.day == value.day) {
      return DateFormat('HH:mm').format(value);
    }
    return DateFormat('dd/MM/yyyy').format(value);
  }

  @override
  Widget build(BuildContext context) {
    final (IconData icon, Color color) = switch (item.kind) {
      'RESERVA_CONFIRMADA' => (Icons.check_circle, const Color(0xFF047857)),
      'RESERVA_VENCIDA' => (Icons.timer_off_outlined, const Color(0xFFB45309)),
      'RESERVA_CANCELADA' => (Icons.event_busy_outlined, AppTheme.errorColor),
      'RECORDATORIO_24H' ||
      'RECORDATORIO_2H' => (Icons.alarm_outlined, AppTheme.accentDark),
      'PAGO_REVISION' => (Icons.report_outlined, AppTheme.errorColor),
      'COMUNICACION' => (Icons.mail_outline, AppTheme.accentDark),
      _ => (Icons.info_outline, AppTheme.textSecondary),
    };
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
      child: Material(
        color: item.read ? Colors.white : AppTheme.demoBg,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: BorderSide(
            color: item.read
                ? const Color(0xFFDCE8DF)
                : const Color(0xFF8ABDA2),
          ),
        ),
        clipBehavior: Clip.antiAlias,
        child: ListTile(
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 16,
            vertical: 12,
          ),
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
              fontSize: 17,
            ),
          ),
          subtitle: item.isCommunication || item.promotionId != null
              ? Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.sender?.trim().isNotEmpty == true
                          ? item.sender!
                          : 'SITUR-SMART',
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: Color(0xFF397657),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      item.message,
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Leer mensaje →',
                      style: TextStyle(
                        color: Color(0xFF287450),
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                )
              : Text(item.message),
          trailing: Text(
            _when(item.createdAt),
            style: const TextStyle(fontSize: 12),
          ),
          isThreeLine: true,
        ),
      ),
    );
  }
}

class _CommunicationMetadata extends StatelessWidget {
  const _CommunicationMetadata({required this.item});

  final AppNotification item;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Tipo: ${item.communicationTypeLabel}'),
        Text('Remitente: ${_value(item.sender)}'),
        Text('Motivo: ${_value(item.reason)}'),
        if (item.expiresAt != null)
          Text(
            item.expired
                ? 'Oferta o aviso vencido'
                : 'Válido hasta: ${DateFormat('dd/MM/yyyy HH:mm').format(item.expiresAt!)}',
          ),
      ],
    );
  }

  static String _value(String? value) =>
      value == null || value.trim().isEmpty ? 'No especificado' : value;
}

/// El cuerpo se toma de la bandeja; no depende del texto abreviado del push.
class _CommunicationDetails extends StatelessWidget {
  const _CommunicationDetails({
    required this.item,
    this.onOpenBooking,
    this.onOpenOffer,
  });

  final AppNotification item;
  final VoidCallback? onOpenBooking;
  final VoidCallback? onOpenOffer;

  @override
  Widget build(BuildContext context) {
    return FractionallySizedBox(
      heightFactor: 0.9,
      child: Column(
        children: [
          Align(
            alignment: Alignment.centerRight,
            child: IconButton(
              tooltip: 'Cerrar comunicación',
              onPressed: () => Navigator.of(context).pop(),
              icon: const Icon(Icons.close),
            ),
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.title,
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: const Color(0xFF104F40),
                    ),
                  ),
                  const SizedBox(height: 16),
                  _CommunicationMetadata(item: item),
                  const Divider(height: 32),
                  SelectableText(
                    item.message,
                    style: const TextStyle(fontSize: 17, height: 1.7),
                  ),
                ],
              ),
            ),
          ),
          if (onOpenBooking != null)
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: FilledButton.icon(
                  onPressed: onOpenBooking,
                  icon: const Icon(Icons.luggage_outlined),
                  label: const Text('Ver reserva'),
                ),
              ),
            ),
          if (onOpenOffer != null)
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: FilledButton.icon(
                  onPressed: onOpenOffer,
                  icon: const Icon(Icons.local_offer_outlined),
                  label: const Text('Ver oferta'),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
