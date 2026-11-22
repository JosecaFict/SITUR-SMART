import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/features/notificaciones/data/communication_preferences_service.dart';
import 'package:mobile/features/notificaciones/data/notifications_store.dart';
import 'package:mobile/features/notificaciones/presentation/communication_preferences_sheet.dart';

class _Preferences extends CommunicationPreferencesService {
  Completer<List<CommunicationPreference>>? pending;
  int? company;
  bool? enabled;

  @override
  Future<List<CommunicationPreference>> load() async => const [
    CommunicationPreference(
      companyId: 7,
      name: 'Hotel de prueba',
      enabled: false,
    ),
  ];

  @override
  Future<List<CommunicationPreference>> save(int? companyId, bool value) {
    company = companyId;
    enabled = value;
    return pending!.future;
  }
}

void main() {
  test(
    'la promoción conserva vencimiento e identificador al marcar lectura',
    () {
      final item = AppNotification.fromJson({
        'id': 1,
        'tipo': 'COMUNICACION',
        'datos': {
          'tipo_comunicacion': 'PROMOCIONAL',
          'promocion_id': 12,
          'vence_en': DateTime.now()
              .subtract(const Duration(minutes: 1))
              .toIso8601String(),
        },
      }).copyWith(read: true);
      expect(item.communicationTypeLabel, 'Promocional');
      expect(item.promotionId, 12);
      expect(item.expired, isTrue);
      expect(item.read, isTrue);
    },
  );

  testWidgets(
    'el consentimiento solo cambia tras guardar y bloquea dobles envíos',
    (tester) async {
      final service = _Preferences()..pending = Completer();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: CommunicationPreferencesSheet(service: service)),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('avisos de reservas'), findsOneWidget);
      await tester.tap(find.byType(Switch));
      await tester.pump();
      expect(service.company, 7);
      expect(service.enabled, isTrue);
      expect(
        tester.widget<SwitchListTile>(find.byType(SwitchListTile)).value,
        isFalse,
      );
      expect(
        tester.widget<SwitchListTile>(find.byType(SwitchListTile)).onChanged,
        isNull,
      );
      service.pending!.complete(const [
        CommunicationPreference(
          companyId: 7,
          name: 'Hotel de prueba',
          enabled: true,
        ),
      ]);
      await tester.pumpAndSettle();
      expect(
        tester.widget<SwitchListTile>(find.byType(SwitchListTile)).value,
        isTrue,
      );
    },
  );

  testWidgets('fallo de guardado conserva preferencia y permite reintentar', (
    tester,
  ) async {
    final service = _Preferences()..pending = Completer();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: CommunicationPreferencesSheet(service: service)),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byType(Switch));
    await tester.pump();
    service.pending!.completeError(Exception('sin red'));
    await tester.pumpAndSettle();
    expect(find.textContaining('No se guardó'), findsOneWidget);
    expect(
      tester.widget<SwitchListTile>(find.byType(SwitchListTile)).value,
      isFalse,
    );
    expect(
      tester.widget<SwitchListTile>(find.byType(SwitchListTile)).onChanged,
      isNotNull,
    );
  });
}
