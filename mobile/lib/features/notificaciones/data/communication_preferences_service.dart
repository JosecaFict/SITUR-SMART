import '../../../core/network/api_client.dart';

class CommunicationPreference {
  const CommunicationPreference({
    required this.companyId,
    required this.name,
    required this.enabled,
  });
  final int? companyId;
  final String name;
  final bool enabled;

  factory CommunicationPreference.fromJson(Map<String, dynamic> json) =>
      CommunicationPreference(
        companyId: int.tryParse('${json['empresa_id'] ?? ''}'),
        name: json['nombre']?.toString() ?? 'SITUR-SMART',
        enabled: json['promociones'] == true,
      );
}

class CommunicationPreferencesService {
  CommunicationPreferencesService({ApiClient? api}) : _api = api ?? ApiClient();
  final ApiClient _api;
  static const _path = 'me/comunicaciones/preferencias/';

  List<CommunicationPreference> _parse(Map<String, dynamic> data) => [
    for (final row in data['preferencias'] as List<dynamic>? ?? [])
      if (row is Map<String, dynamic>) CommunicationPreference.fromJson(row),
  ];

  Future<List<CommunicationPreference>> load() async =>
      _parse(await _api.getMap(_path, ''));

  Future<List<CommunicationPreference>> save(
    int? companyId,
    bool enabled,
  ) async => _parse(
    await _api.patchAuth(_path, {
      'empresa_id': companyId,
      'promociones': enabled,
    }),
  );
}
