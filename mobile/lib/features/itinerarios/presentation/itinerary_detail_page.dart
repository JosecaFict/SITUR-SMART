import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../marketplace/presentation/widgets/marketplace_widgets.dart';
import '../data/itinerary_models.dart';
import '../data/itinerary_service.dart';
import 'activity_sheet.dart';
import 'itineraries_view.dart';
import 'itinerary_form_sheet.dart';

/// Un viaje día por día: sus reservas pagadas y las actividades del turista.
class ItineraryDetailPage extends StatefulWidget {
  const ItineraryDetailPage({super.key, required this.itineraryId, this.service});

  final int itineraryId;
  final ItineraryService? service;

  @override
  State<ItineraryDetailPage> createState() => _ItineraryDetailPageState();
}

enum _Menu { edit, delete }

class _ItineraryDetailPageState extends State<ItineraryDetailPage> {
  static final DateFormat _dayFormat = DateFormat('EEEE d MMM', 'es');

  late final ItineraryService _service = widget.service ?? ItineraryService();

  ItineraryDetail? _detail;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = _detail == null;
      _error = null;
    });
    try {
      final detail = await _service.detail(widget.itineraryId);
      if (!mounted) return;
      setState(() {
        _detail = detail;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = error is ApiException ? error.message : 'No se pudo cargar el itinerario.';
      });
    }
  }

  void _toast(String message) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));

  Future<void> _menu(_Menu action) async {
    final detail = _detail;
    if (detail == null) return;
    if (action == _Menu.edit) {
      final saved = await showItineraryForm(context, initial: detail.summary, service: _service);
      if (saved != null && mounted) setState(() => _detail = saved);
      return;
    }
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('¿Eliminar el itinerario?'),
        content: const Text('Se borran sus actividades. Tus reservas no se tocan.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancelar')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Eliminar')),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await _service.delete(detail.summary.id);
      if (mounted) context.pop();
    } catch (error) {
      _toast(error is ApiException ? error.message : 'No se pudo eliminar.');
    }
  }

  Future<void> _addTo(DateTime day) async {
    final saved = await showActivitySheet(context, itinerary: _detail!.summary, day: day, service: _service);
    if (saved == true) _load();
  }

  Future<void> _itemActions(AgendaItem item, DateTime day) async {
    final action = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (item.route != null)
              ListTile(
                leading: const Icon(Icons.open_in_new),
                title: Text(item.isLodging ? 'Ver el hospedaje' : 'Ver el producto'),
                onTap: () => Navigator.pop(context, 'open'),
              ),
            ListTile(
              leading: const Icon(Icons.edit_outlined),
              title: const Text('Editar'),
              onTap: () => Navigator.pop(context, 'edit'),
            ),
            ListTile(
              leading: const Icon(Icons.delete_outline),
              title: const Text('Quitar del itinerario'),
              onTap: () => Navigator.pop(context, 'delete'),
            ),
          ],
        ),
      ),
    );
    if (!mounted || action == null) return;
    switch (action) {
      case 'open':
        await context.push(item.route!);
      case 'edit':
        final saved = await showActivitySheet(
          context,
          itinerary: _detail!.summary,
          day: day,
          initial: item,
          productName: item.product?.nombre,
          service: _service,
        );
        if (saved == true) _load();
      case 'delete':
        try {
          await _service.deleteActivity(_detail!.summary.id, item.id);
          _load();
        } catch (error) {
          _toast(error is ApiException ? error.message : 'No se pudo quitar la actividad.');
        }
    }
  }

  @override
  Widget build(BuildContext context) {
    final detail = _detail;
    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppTheme.accentDark,
        foregroundColor: Colors.white,
        title: Text(detail?.summary.name ?? 'Itinerario', style: const TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          if (detail != null)
            PopupMenuButton<_Menu>(
              onSelected: _menu,
              itemBuilder: (_) => const [
                PopupMenuItem(value: _Menu.edit, child: Text('Editar viaje')),
                PopupMenuItem(value: _Menu.delete, child: Text('Eliminar')),
              ],
            ),
        ],
      ),
      body: _body(),
    );
  }

  Widget _body() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    final detail = _detail;
    if (_error != null || detail == null) {
      return ErrorRetry(message: _error ?? 'No se pudo cargar el itinerario.', onRetry: _load);
    }
    final summary = detail.summary;
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          InfoLine(icon: Icons.date_range, text: itineraryDates(summary.start, summary.end)),
          if (summary.city != null) InfoLine(icon: Icons.place_outlined, text: summary.city!),
          if (summary.notes != null) InfoLine(icon: Icons.sticky_note_2_outlined, text: summary.notes!),
          const SizedBox(height: 8),
          for (final day in detail.agenda) _dayCard(day),
        ],
      ),
    );
  }

  Widget _dayCard(ItineraryDay day) {
    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  toBeginningOfSentenceCase(_dayFormat.format(day.date)),
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
                ),
              ),
              TextButton.icon(
                onPressed: () => _addTo(day.date),
                icon: const Icon(Icons.add, size: 18),
                label: const Text('Agregar'),
              ),
            ],
          ),
          if (day.isEmpty)
            const Padding(
              padding: EdgeInsets.only(left: 4, bottom: 4),
              child: Text('Día libre', style: TextStyle(color: AppTheme.textSecondary)),
            ),
          for (final item in day.items) _AgendaTile(item: item, onTap: () => _tap(item, day.date)),
        ],
      ),
    );
  }

  Future<void> _tap(AgendaItem item, DateTime day) async {
    if (item.isBooking) {
      await context.push(item.route!);
      if (mounted) _load();
      return;
    }
    await _itemActions(item, day);
  }
}

class _AgendaTile extends StatelessWidget {
  const _AgendaTile({required this.item, required this.onTap});

  final AgendaItem item;
  final VoidCallback onTap;

  IconData get _icon {
    if (item.isBooking) {
      if (item.moment == 'LLEGADA') return Icons.login;
      if (item.moment == 'SALIDA') return Icons.logout;
      return Icons.confirmation_number_outlined;
    }
    if (item.kind == 'PRODUCTO') return item.isLodging ? Icons.hotel_outlined : Icons.landscape_outlined;
    return Icons.edit_note;
  }

  String? get _subtitle {
    if (item.isBooking) {
      final moment = switch (item.moment) {
        'LLEGADA' => 'Llegada',
        'SALIDA' => 'Salida',
        _ => 'Reserva',
      };
      return '$moment · ${item.bookingCode ?? ''} · Pagada';
    }
    return item.note;
  }

  @override
  Widget build(BuildContext context) {
    final subtitle = _subtitle;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      elevation: 0,
      color: item.isBooking ? AppTheme.demoBg : null,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: item.isBooking ? AppTheme.demoBorder : AppTheme.inputBorder),
      ),
      child: ListTile(
        onTap: onTap,
        leading: SizedBox(
          width: 48,
          child: item.time != null
              ? Text(item.time!, style: const TextStyle(fontWeight: FontWeight.w700, color: AppTheme.accentDark))
              : Icon(_icon, color: AppTheme.accentDark),
        ),
        title: Text(item.title, style: const TextStyle(fontWeight: FontWeight.w600, color: AppTheme.titleColor)),
        subtitle: subtitle == null ? null : Text(subtitle),
        trailing: Icon(item.isBooking ? Icons.chevron_right : Icons.more_vert, size: 20),
      ),
    );
  }
}
