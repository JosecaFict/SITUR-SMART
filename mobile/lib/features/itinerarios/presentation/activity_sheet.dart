import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../core/network/api_client.dart';
import '../data/itinerary_models.dart';
import '../data/itinerary_service.dart';

/// Agrega una actividad a [itinerary], o edita [initial].
///
/// Con [productId] la actividad es ese producto del Marketplace y el título es
/// opcional (si queda vacío, el backend usa el nombre del producto).
/// Devuelve true si se guardó.
Future<bool?> showActivitySheet(
  BuildContext context, {
  required ItinerarySummary itinerary,
  DateTime? day,
  AgendaItem? initial,
  int? productId,
  String? productName,
  ItineraryService? service,
}) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => ActivitySheet(
      itinerary: itinerary,
      day: day,
      initial: initial,
      productId: productId,
      productName: productName,
      service: service,
    ),
  );
}

class ActivitySheet extends StatefulWidget {
  const ActivitySheet({
    super.key,
    required this.itinerary,
    this.day,
    this.initial,
    this.productId,
    this.productName,
    this.service,
  });

  final ItinerarySummary itinerary;
  final DateTime? day;
  final AgendaItem? initial;
  final int? productId;
  final String? productName;
  final ItineraryService? service;

  @override
  State<ActivitySheet> createState() => _ActivitySheetState();
}

class _ActivitySheetState extends State<ActivitySheet> {
  static final DateFormat _dayFormat = DateFormat('EEEE d MMM', 'es');

  late final ItineraryService _service = widget.service ?? ItineraryService();
  late final TextEditingController _title = TextEditingController(text: widget.initial?.title);
  late final TextEditingController _note = TextEditingController(text: widget.initial?.note);
  late final List<DateTime> _days = [
    for (var i = 0; i < widget.itinerary.days; i++) widget.itinerary.start.add(Duration(days: i)),
  ];
  late DateTime _day = _initialDay();
  late TimeOfDay? _time = _parseTime(widget.initial?.time);

  bool _saving = false;
  String? _error;

  bool get _editing => widget.initial != null;
  bool get _isProduct => widget.productId != null || widget.initial?.kind == 'PRODUCTO';

  DateTime _initialDay() {
    final wanted = widget.day;
    if (wanted != null) {
      for (final day in _days) {
        if (DateUtils.isSameDay(day, wanted)) return day;
      }
    }
    return _days.first;
  }

  static TimeOfDay? _parseTime(String? value) {
    if (value == null) return null;
    final parts = value.split(':');
    if (parts.length < 2) return null;
    final hour = int.tryParse(parts[0]);
    final minute = int.tryParse(parts[1]);
    return hour == null || minute == null ? null : TimeOfDay(hour: hour, minute: minute);
  }

  static String? _apiTime(TimeOfDay? time) => time == null
      ? null
      : '${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}';

  @override
  void dispose() {
    _title.dispose();
    _note.dispose();
    super.dispose();
  }

  Future<void> _pickTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _time ?? const TimeOfDay(hour: 9, minute: 0),
      helpText: 'Hora',
    );
    if (picked != null) setState(() => _time = picked);
  }

  Future<void> _save() async {
    final title = _title.text.trim();
    if (title.isEmpty && !(_isProduct && !_editing)) {
      setState(() => _error = 'Escribe qué vas a hacer.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    final note = _note.text.trim().isEmpty ? null : _note.text.trim();
    try {
      if (_editing) {
        await _service.updateActivity(widget.itinerary.id, widget.initial!.id,
            day: _day, time: _apiTime(_time), title: title, note: note);
      } else {
        await _service.addActivity(widget.itinerary.id,
            day: _day,
            time: _apiTime(_time),
            productId: widget.productId,
            title: title.isEmpty ? null : title,
            note: note);
      }
      if (mounted) Navigator.of(context).pop(true);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = error is ApiException ? error.message : 'No se pudo guardar la actividad.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final time = _time;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(_editing ? 'Editar actividad' : 'Agregar a ${widget.itinerary.name}',
                style: Theme.of(context).textTheme.titleLarge),
            if (widget.productName != null) ...[
              const SizedBox(height: 4),
              Text(widget.productName!, style: const TextStyle(fontWeight: FontWeight.w600)),
            ],
            const SizedBox(height: 16),
            DropdownButtonFormField<DateTime>(
              initialValue: _day,
              decoration: const InputDecoration(labelText: 'Día'),
              items: [
                for (final day in _days)
                  DropdownMenuItem(value: day, child: Text(toBeginningOfSentenceCase(_dayFormat.format(day)))),
              ],
              onChanged: (value) => setState(() => _day = value ?? _day),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _pickTime,
                    icon: const Icon(Icons.schedule),
                    label: Text(time == null ? 'Sin hora' : time.format(context)),
                  ),
                ),
                if (time != null)
                  IconButton(
                    tooltip: 'Quitar la hora',
                    onPressed: () => setState(() => _time = null),
                    icon: const Icon(Icons.close),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _title,
              maxLength: 150,
              textCapitalization: TextCapitalization.sentences,
              decoration: InputDecoration(
                labelText: _isProduct && !_editing ? 'Título (opcional)' : 'Qué vas a hacer',
                hintText: _isProduct ? widget.productName : 'Comprar recuerdos',
              ),
            ),
            TextField(
              controller: _note,
              minLines: 1,
              maxLines: 3,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(labelText: 'Nota (opcional)'),
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
                  : Text(_editing ? 'Guardar' : 'Agregar'),
            ),
          ],
        ),
      ),
    );
  }
}
