import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../marketplace/presentation/widgets/marketplace_widgets.dart';
import '../data/itinerary_models.dart';
import '../data/itinerary_service.dart';
import 'itinerary_form_sheet.dart';

/// "6 – 9 oct 2026" o "28 sep – 2 oct 2026".
String itineraryDates(DateTime start, DateTime end) {
  final sameMonth = start.year == end.year && start.month == end.month;
  final first = DateFormat(sameMonth ? 'd' : (start.year == end.year ? 'd MMM' : 'd MMM yyyy'), 'es').format(start);
  return '$first – ${DateFormat('d MMM yyyy', 'es').format(end)}';
}

/// Pestaña Itinerarios de Mis viajes: los planes del turista, próximos arriba.
class ItinerariesView extends StatefulWidget {
  const ItinerariesView({super.key, this.service});

  final ItineraryService? service;

  @override
  State<ItinerariesView> createState() => _ItinerariesViewState();
}

class _ItinerariesViewState extends State<ItinerariesView> {
  late final ItineraryService _service = widget.service ?? ItineraryService();

  List<ItinerarySummary> _items = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = _items.isEmpty;
      _error = null;
    });
    try {
      final items = await _service.list();
      if (!mounted) return;
      setState(() {
        _items = items;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = error is ApiException ? error.message : 'No se pudieron cargar tus itinerarios.';
      });
    }
  }

  Future<void> _create() async {
    final created = await showItineraryForm(context, service: _service);
    if (created == null || !mounted) return;
    await context.push('/itinerario/${created.summary.id}');
    if (mounted) _load();
  }

  Future<void> _open(ItinerarySummary itinerary) async {
    await context.push('/itinerario/${itinerary.id}');
    if (mounted) _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      floatingActionButton: FloatingActionButton.extended(
        heroTag: 'nuevo-itinerario',
        onPressed: _create,
        backgroundColor: AppTheme.accentDark,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add),
        label: const Text('Nuevo'),
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
              icon: Icons.map_outlined,
              title: 'Arma tu primer itinerario',
              message: 'Planifica tu viaje día por día. Tus reservas pagadas aparecen solas en su día.',
            ),
          ],
        ),
      );
    }

    final upcoming = _items.where((i) => !i.past).toList()..sort((a, b) => a.start.compareTo(b.start));
    final past = _items.where((i) => i.past).toList();
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
        children: [
          for (final itinerary in upcoming) _card(itinerary),
          if (past.isNotEmpty) ...[
            Padding(
              padding: const EdgeInsets.fromLTRB(4, 16, 4, 8),
              child: Text('Anteriores', style: Theme.of(context).textTheme.titleLarge),
            ),
            for (final itinerary in past) _card(itinerary),
          ],
        ],
      ),
    );
  }

  Widget _card(ItinerarySummary itinerary) {
    final details = [
      if (itinerary.city != null) itinerary.city!,
      '${itinerary.days} ${itinerary.days == 1 ? 'día' : 'días'}',
      '${itinerary.activities} ${itinerary.activities == 1 ? 'actividad' : 'actividades'}',
    ].join(' · ');
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Card(
        margin: EdgeInsets.zero,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppTheme.inputBorder),
        ),
        child: ListTile(
          onTap: () => _open(itinerary),
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          leading: const CircleAvatar(
            backgroundColor: AppTheme.demoBg,
            foregroundColor: AppTheme.accentDark,
            child: Icon(Icons.map_outlined),
          ),
          title: Text(itinerary.name, style: const TextStyle(fontWeight: FontWeight.w700, color: AppTheme.titleColor)),
          subtitle: Text('${itineraryDates(itinerary.start, itinerary.end)}\n$details'),
          isThreeLine: true,
          trailing: const Icon(Icons.chevron_right),
        ),
      ),
    );
  }
}
