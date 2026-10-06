import '../../../core/network/api_client.dart';
import 'itinerary_models.dart';

/// Itinerarios del turista (me/itinerarios/).
class ItineraryService {
  ItineraryService({ApiClient? apiClient}) : _api = apiClient ?? ApiClient();

  final ApiClient _api;

  static const _base = 'me/itinerarios/';

  Future<List<ItinerarySummary>> list() async {
    final data = await _api.getList(_base, '');
    return data.whereType<Map<String, dynamic>>().map(ItinerarySummary.fromJson).toList();
  }

  Future<ItineraryDetail> detail(int id) async => ItineraryDetail.fromJson(await _api.getMap('$_base$id/', ''));

  Future<ItineraryDetail> create({
    required String name,
    required DateTime start,
    required DateTime end,
    int? cityId,
    String? notes,
  }) async =>
      ItineraryDetail.fromJson(await _api.postAuth(_base, {
        'nombre': name,
        'inicio': apiDate(start),
        'fin': apiDate(end),
        'ciudad_id': cityId,
        'notas': notes,
      }));

  Future<ItineraryDetail> update(
    int id, {
    required String name,
    required DateTime start,
    required DateTime end,
    int? cityId,
    String? notes,
  }) async =>
      ItineraryDetail.fromJson(await _api.patchAuth('$_base$id/', {
        'nombre': name,
        'inicio': apiDate(start),
        'fin': apiDate(end),
        'ciudad_id': cityId,
        'notas': notes,
      }));

  Future<void> delete(int id) => _api.deleteAuth('$_base$id/');

  /// Una actividad libre ([title]) o un producto del Marketplace ([productId]).
  Future<void> addActivity(
    int itineraryId, {
    required DateTime day,
    String? time,
    int? productId,
    String? title,
    String? note,
  }) =>
      _api.postAuth('$_base$itineraryId/actividades/', {
        'fecha': apiDate(day),
        'hora': time,
        'producto_id': productId,
        'titulo': title,
        'nota': note,
      });

  Future<void> updateActivity(
    int itineraryId,
    int activityId, {
    required DateTime day,
    String? time,
    required String title,
    String? note,
  }) =>
      _api.patchAuth('$_base$itineraryId/actividades/$activityId/', {
        'fecha': apiDate(day),
        'hora': time,
        'titulo': title,
        'nota': note,
      });

  Future<void> deleteActivity(int itineraryId, int activityId) =>
      _api.deleteAuth('$_base$itineraryId/actividades/$activityId/');
}
