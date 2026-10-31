import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:mobile/features/resenas/data/reviews_service.dart';
import 'package:mobile/features/resenas/presentation/product_reviews.dart';

Map<String, dynamic> _reviewJson({
  int id = 1,
  int rating = 4,
  String comment = 'Muy buena experiencia',
}) => {
  'id': id,
  'producto_id': 9,
  'autor': 'Ana Turista',
  'es_propia': false,
  'calificacion': rating,
  'comentario': comment,
  'creado_en': '2026-10-31T12:00:00-04:00',
  'actualizado_en': '2026-10-31T12:00:00-04:00',
};

ReviewsPage _page({List<ProductReview>? items}) => ReviewsPage(
  items: items ?? [ProductReview.fromJson(_reviewJson())],
  count: items?.length ?? 2,
  hasNext: false,
  distribution: const {1: 0, 2: 0, 3: 0, 4: 1, 5: 1},
);

class _FakeReviewsService extends ReviewsService {
  _FakeReviewsService({required this.session, ProductReview? own})
    : ownReview = own;

  final bool session;
  ProductReview? ownReview;
  int creates = 0;
  int updates = 0;
  int deletes = 0;

  @override
  Future<ReviewsPage> list(int productId, {int page = 1}) async => _page();

  @override
  Future<bool> hasSession() async => session;

  @override
  Future<ProductReview?> own(int productId) async => ownReview;

  @override
  Future<ProductReview> create(
    int productId,
    int rating,
    String comment,
  ) async {
    creates++;
    return ownReview = ProductReview.fromJson(
      _reviewJson(id: 7, rating: rating, comment: comment)
        ..['es_propia'] = true,
    );
  }

  @override
  Future<ProductReview> update(int reviewId, int rating, String comment) async {
    updates++;
    return ownReview = ProductReview.fromJson(
      _reviewJson(id: reviewId, rating: rating, comment: comment)
        ..['es_propia'] = true,
    );
  }

  @override
  Future<void> delete(int reviewId) async {
    deletes++;
    ownReview = null;
  }
}

void main() {
  test('interpreta reseñas, distribución y promedio', () {
    final page = ReviewsPage.fromJson({
      'count': 2,
      'next': null,
      'results': [_reviewJson()],
      'distribucion_calificaciones': {'1': 0, '2': 0, '3': 0, '4': 1, '5': 1},
    });
    expect(page.items.single.author, 'Ana Turista');
    expect(page.items.single.rating, 4);
    expect(page.average, 4.5);
  });

  testWidgets(
    'un visitante consulta reseñas pero debe iniciar sesión para publicar',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: ProductReviews(
                productId: 9,
                service: _FakeReviewsService(session: false),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Ana Turista'), findsOneWidget);
      expect(
        find.text('Inicia sesión para publicar tu reseña.'),
        findsOneWidget,
      );
      expect(find.text('Escribir una reseña'), findsNothing);
    },
  );

  testWidgets('un turista autenticado publica una reseña válida', (
    tester,
  ) async {
    final service = _FakeReviewsService(session: true);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: ProductReviews(productId: 9, service: service),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final fiveStars = find.byWidgetPredicate(
      (widget) =>
          widget is IconButton &&
          widget.tooltip == '5 estrellas' &&
          widget.onPressed != null,
    );
    await tester.tap(fiveStars);
    await tester.enterText(find.byType(TextField), 'Excelente atención');
    await tester.tap(find.widgetWithText(FilledButton, 'Publicar'));
    await tester.pumpAndSettle();

    expect(service.creates, 1);
    expect(find.text('Tu reseña'), findsOneWidget);
    expect(find.text('Excelente atención'), findsOneWidget);
  });
}
