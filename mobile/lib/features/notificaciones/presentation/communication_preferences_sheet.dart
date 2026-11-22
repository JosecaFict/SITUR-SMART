import 'package:flutter/material.dart';

import '../data/communication_preferences_service.dart';

class CommunicationPreferencesSheet extends StatefulWidget {
  const CommunicationPreferencesSheet({super.key, this.service});
  final CommunicationPreferencesService? service;

  @override
  State<CommunicationPreferencesSheet> createState() =>
      _CommunicationPreferencesSheetState();
}

class _CommunicationPreferencesSheetState
    extends State<CommunicationPreferencesSheet> {
  late final _service = widget.service ?? CommunicationPreferencesService();
  List<CommunicationPreference> _items = [];
  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final items = await _service.load();
      if (mounted) {
        setState(() {
          _items = items;
          _loading = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'No se pudieron cargar las preferencias.';
          _loading = false;
        });
      }
    }
  }

  Future<void> _save(CommunicationPreference item, bool enabled) async {
    if (_saving) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final items = await _service.save(item.companyId, enabled);
      if (mounted) {
        setState(() {
          _items = items;
          _saving = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'No se guardó el cambio. Inténtalo nuevamente.';
          _saving = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => FractionallySizedBox(
    heightFactor: 0.85,
    child: Column(
      children: [
        ListTile(
          title: const Text('Preferencias de promociones'),
          trailing: IconButton(
            tooltip: 'Cerrar preferencias',
            onPressed: () => Navigator.of(context).pop(),
            icon: const Icon(Icons.close),
          ),
        ),
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 20),
          child: Text(
            'Elige de quién recibir ofertas. Los avisos de reservas y las comunicaciones internas seguirán llegando.',
          ),
        ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
        if (_loading)
          const Expanded(child: Center(child: CircularProgressIndicator()))
        else
          Expanded(
            child: ListView(
              children: [
                for (final item in _items)
                  SwitchListTile(
                    title: Text(item.name),
                    value: item.enabled,
                    onChanged: _saving
                        ? null
                        : (enabled) => _save(item, enabled),
                  ),
                TextButton(
                  onPressed: _saving ? null : _load,
                  child: const Text('Actualizar preferencias'),
                ),
              ],
            ),
          ),
      ],
    ),
  );
}
