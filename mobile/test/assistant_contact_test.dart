import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/features/asistente/data/assistant_service.dart';

Map<String, dynamic> card(Object? contacto) => {
      'id': 3,
      'nombre': 'Hotel Sal',
      'tipo': 'Hotel',
      'ciudad': 'Uyuni',
      'moneda': 'Bs',
      'contacto': contacto,
    };

void main() {
  test('lee el enlace de WhatsApp de la empresa', () {
    final lodging = AssistantLodging.fromJson(card({
      'telefono': '71234567',
      'whatsapp': true,
      'whatsapp_url': 'https://wa.me/59171234567?text=Hola',
      'email': null,
    }));
    expect(lodging.whatsappUrl, 'https://wa.me/59171234567?text=Hola');
    expect(lodging.telefono, '71234567');
    expect(lodging.hasContact, isTrue);
  });

  test('un fijo queda solo como telefono', () {
    final lodging = AssistantLodging.fromJson(card({
      'telefono': '3-3456789',
      'whatsapp': false,
      'whatsapp_url': null,
      'email': null,
    }));
    expect(lodging.whatsappUrl, isNull);
    expect(lodging.telefono, '3-3456789');
  });

  test('sin contacto no muestra nada', () {
    final lodging = AssistantLodging.fromJson(card(null));
    expect(lodging.hasContact, isFalse);
  });
}
