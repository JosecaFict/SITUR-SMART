import 'package:flutter/material.dart';

import '../../../core/network/api_client.dart';
import '../data/itinerary_models.dart';
import '../data/itinerary_service.dart';
import 'activity_sheet.dart';
import 'itineraries_view.dart';
import 'itinerary_form_sheet.dart';

/// Desde la ficha de un producto: elegir un itinerario (o crear uno) y el día.
Future<void> addProductToItinerary(
  BuildContext context, {
  required int productId,
  required String productName,
  ItineraryService? service,
}) async {
  final itineraryService = service ?? ItineraryService();
  final messenger = ScaffoldMessenger.of(context);

  final picked = await showModalBottomSheet<_Pick>(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    builder: (_) => _ItineraryPicker(service: itineraryService),
  );
  if (picked == null || !context.mounted) return;

  var itinerary = picked.itinerary;
  if (picked.createNew) {
    final created = await showItineraryForm(context, service: itineraryService);
    if (created == null || !context.mounted) return;
    itinerary = created.summary;
  }

  final saved = await showActivitySheet(
    context,
    itinerary: itinerary!,
    productId: productId,
    productName: productName,
    service: itineraryService,
  );
  if (saved == true) {
    messenger.showSnackBar(SnackBar(content: Text('Agregado a ${itinerary.name}.')));
  }
}

class _Pick {
  const _Pick.existing(this.itinerary) : createNew = false;
  const _Pick.create()
      : itinerary = null,
        createNew = true;

  final ItinerarySummary? itinerary;
  final bool createNew;
}

class _ItineraryPicker extends StatefulWidget {
  const _ItineraryPicker({required this.service});

  final ItineraryService service;

  @override
  State<_ItineraryPicker> createState() => _ItineraryPickerState();
}

class _ItineraryPickerState extends State<_ItineraryPicker> {
  List<ItinerarySummary>? _items;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final items = await widget.service.list();
      if (!mounted) return;
      // Solo los viajes que todavía no terminaron, el más cercano primero.
      setState(() => _items = items.where((i) => !i.past).toList()..sort((a, b) => a.start.compareTo(b.start)));
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error is ApiException ? error.message : 'No se pudieron cargar tus itinerarios.');
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = _items;
    return SafeArea(
      child: ConstrainedBox(
        constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * 0.7),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
              child: Text('Agregar a un itinerario', style: Theme.of(context).textTheme.titleLarge),
            ),
            if (_error != null)
              Padding(padding: const EdgeInsets.all(20), child: Text(_error!))
            else if (items == null)
              const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator()))
            else
              Flexible(
                child: ListView(
                  shrinkWrap: true,
                  children: [
                    for (final itinerary in items)
                      ListTile(
                        leading: const Icon(Icons.map_outlined),
                        title: Text(itinerary.name),
                        subtitle: Text(itineraryDates(itinerary.start, itinerary.end)),
                        onTap: () => Navigator.pop(context, _Pick.existing(itinerary)),
                      ),
                  ],
                ),
              ),
            ListTile(
              leading: const Icon(Icons.add),
              title: const Text('Nuevo itinerario'),
              onTap: () => Navigator.pop(context, const _Pick.create()),
            ),
          ],
        ),
      ),
    );
  }
}
