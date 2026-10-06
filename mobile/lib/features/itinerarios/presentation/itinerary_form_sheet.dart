import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../core/network/api_client.dart';
import '../../marketplace/data/marketplace_service.dart';
import '../../marketplace/models/marketplace_models.dart';
import '../data/itinerary_models.dart';
import '../data/itinerary_service.dart';

/// Crea un itinerario, o edita [initial]. Devuelve el itinerario guardado.
Future<ItineraryDetail?> showItineraryForm(
  BuildContext context, {
  ItinerarySummary? initial,
  ItineraryService? service,
}) {
  return showModalBottomSheet<ItineraryDetail>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => ItineraryFormSheet(initial: initial, service: service),
  );
}

class ItineraryFormSheet extends StatefulWidget {
  const ItineraryFormSheet({super.key, this.initial, this.service, this.marketplace});

  final ItinerarySummary? initial;
  final ItineraryService? service;
  final MarketplaceService? marketplace;

  @override
  State<ItineraryFormSheet> createState() => _ItineraryFormSheetState();
}

class _ItineraryFormSheetState extends State<ItineraryFormSheet> {
  static final DateFormat _format = DateFormat('EEE d MMM yyyy', 'es');

  late final ItineraryService _service = widget.service ?? ItineraryService();
  late final TextEditingController _name = TextEditingController(text: widget.initial?.name);
  late final TextEditingController _notes = TextEditingController(text: widget.initial?.notes);
  late DateTimeRange? _range =
      widget.initial == null ? null : DateTimeRange(start: widget.initial!.start, end: widget.initial!.end);
  late int? _cityId = widget.initial?.cityId;

  List<City> _cities = const [];
  bool _saving = false;
  String? _error;

  bool get _editing => widget.initial != null;

  @override
  void initState() {
    super.initState();
    _loadCities();
  }

  @override
  void dispose() {
    _name.dispose();
    _notes.dispose();
    super.dispose();
  }

  Future<void> _loadCities() async {
    try {
      final cities = await (widget.marketplace ?? MarketplaceService()).cities();
      if (mounted) setState(() => _cities = cities);
    } catch (_) {
      // Sin ciudades el viaje igual se puede crear: la ciudad es opcional.
    }
  }

  Future<void> _pickDates() async {
    final today = DateUtils.dateOnly(DateTime.now());
    final picked = await showDateRangePicker(
      context: context,
      firstDate: _range != null && _range!.start.isBefore(today) ? _range!.start : today,
      lastDate: today.add(const Duration(days: 730)),
      initialDateRange: _range,
      helpText: 'Salida y regreso',
      saveText: 'Listo',
    );
    if (picked != null) setState(() => _range = picked);
  }

  Future<void> _save() async {
    final name = _name.text.trim();
    final range = _range;
    if (name.isEmpty || range == null) {
      setState(() => _error = name.isEmpty ? 'Ponle un nombre al viaje.' : 'Elige las fechas del viaje.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final notes = _notes.text.trim().isEmpty ? null : _notes.text.trim();
      final saved = _editing
          ? await _service.update(widget.initial!.id,
              name: name, start: range.start, end: range.end, cityId: _cityId, notes: notes)
          : await _service.create(name: name, start: range.start, end: range.end, cityId: _cityId, notes: notes);
      if (mounted) Navigator.of(context).pop(saved);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = error is ApiException ? error.message : 'No se pudo guardar el itinerario.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final range = _range;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(_editing ? 'Editar itinerario' : 'Nuevo itinerario', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 16),
            TextField(
              controller: _name,
              textCapitalization: TextCapitalization.sentences,
              maxLength: 120,
              decoration: const InputDecoration(labelText: 'Nombre', hintText: 'Viaje a Santa Cruz'),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: _pickDates,
              icon: const Icon(Icons.date_range),
              label: Text(range == null ? 'Elegir fechas' : '${_format.format(range.start)} → ${_format.format(range.end)}'),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<int?>(
              initialValue: _cities.any((city) => city.id == _cityId) ? _cityId : null,
              decoration: const InputDecoration(labelText: 'Ciudad (opcional)'),
              items: [
                const DropdownMenuItem<int?>(value: null, child: Text('Sin ciudad')),
                for (final city in _cities) DropdownMenuItem<int?>(value: city.id, child: Text(city.nombre)),
              ],
              onChanged: (value) => setState(() => _cityId = value),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _notes,
              minLines: 2,
              maxLines: 4,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(labelText: 'Notas (opcional)', hintText: 'Llevar repelente'),
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ],
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: _saving ? null : _save,
              child: _saving
                  ? const SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : Text(_editing ? 'Guardar' : 'Crear itinerario'),
            ),
          ],
        ),
      ),
    );
  }
}
