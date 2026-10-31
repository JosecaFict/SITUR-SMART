import '../../../core/network/api_client.dart';

int _asInt(Object? value) => value is int ? value : int.tryParse('$value') ?? 0;

class ProductReview {
  const ProductReview({
    required this.id,
    required this.author,
    required this.rating,
    required this.comment,
    required this.createdAt,
    required this.isOwn,
  });

  final int id;
  final String author;
  final int rating;
  final String comment;
  final DateTime createdAt;
  final bool isOwn;

  factory ProductReview.fromJson(Map<String, dynamic> json) => ProductReview(
    id: _asInt(json['id']),
    author: json['autor']?.toString() ?? 'Viajero',
    rating: _asInt(json['calificacion']),
    comment: json['comentario']?.toString() ?? '',
    createdAt:
        DateTime.tryParse('${json['creado_en'] ?? ''}')?.toLocal() ??
        DateTime(1970),
    isOwn: json['es_propia'] == true,
  );
}

class ReviewsPage {
  const ReviewsPage({
    required this.items,
    required this.count,
    required this.hasNext,
    required this.distribution,
  });

  final List<ProductReview> items;
  final int count;
  final bool hasNext;
  final Map<int, int> distribution;

  double? get average {
    if (count == 0) return null;
    var total = 0;
    for (var star = 1; star <= 5; star++) {
      total += star * (distribution[star] ?? 0);
    }
    return total / count;
  }

  factory ReviewsPage.fromJson(Map<String, dynamic> json) {
    final rawItems = json['results'] as List<dynamic>? ?? const [];
    final rawDistribution = json['distribucion_calificaciones'];
    return ReviewsPage(
      items: rawItems
          .whereType<Map<String, dynamic>>()
          .map(ProductReview.fromJson)
          .toList(),
      count: _asInt(json['count']),
      hasNext: json['next'] != null,
      distribution: {
        for (var star = 1; star <= 5; star++)
          star: rawDistribution is Map ? _asInt(rawDistribution['$star']) : 0,
      },
    );
  }
}

class ReviewsService {
  ReviewsService({ApiClient? apiClient}) : _api = apiClient ?? ApiClient();

  final ApiClient _api;

  Future<ReviewsPage> list(int productId, {int page = 1}) async {
    final data = await _api.getPublic(
      'marketplace/productos/$productId/resenas/',
      query: {'page': page},
    );
    if (data is! Map<String, dynamic>) {
      throw const ApiException('El backend no devolvió reseñas válidas.');
    }
    return ReviewsPage.fromJson(data);
  }

  Future<bool> hasSession() async =>
      (await _api.getAccessToken())?.isNotEmpty == true;

  Future<ProductReview?> own(int productId) async {
    final data = await _api.getMap('me/productos/$productId/resena/', '');
    final review = data['resena'];
    return review is Map<String, dynamic>
        ? ProductReview.fromJson(review)
        : null;
  }

  Future<ProductReview> create(
    int productId,
    int rating,
    String comment,
  ) async {
    final data = await _api.postAuth(
      'marketplace/productos/$productId/resenas/',
      {'calificacion': rating, 'comentario': comment},
    );
    return ProductReview.fromJson(data);
  }

  Future<ProductReview> update(int reviewId, int rating, String comment) async {
    final data = await _api.patchAuth('me/resenas/$reviewId/', {
      'calificacion': rating,
      'comentario': comment,
    });
    return ProductReview.fromJson(data);
  }

  Future<void> delete(int reviewId) => _api.deleteAuth('me/resenas/$reviewId/');
}
