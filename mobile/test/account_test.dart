import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:mobile/core/network/api_client.dart';
import 'package:mobile/features/perfil/data/account_service.dart';
import 'package:mobile/features/perfil/presentation/account_security_section.dart';
import 'package:mobile/features/perfil/presentation/email_verification_sheet.dart';

class _FakeAccountService extends AccountService {
  String? confirmed;

  @override
  Future<void> sendEmailCode() async {}

  @override
  Future<void> confirmEmail(String code) async {
    if (code != '123456') throw const ApiException('El código no es correcto.', statusCode: 400);
    confirmed = code;
  }
}

void main() {
  testWidgets('sin correo verificado, Seguridad invita a verificarlo', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: AccountSecuritySection(emailVerified: false, onChanged: () {})),
    ));

    expect(find.textContaining('Tu correo no está verificado'), findsOneWidget);
    expect(find.text('Cambiar contraseña'), findsOneWidget);
    expect(find.text('Sesiones abiertas'), findsOneWidget);
    expect(find.text('Eliminar mi cuenta'), findsOneWidget);
  });

  testWidgets('con el correo verificado no aparece el aviso', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: AccountSecuritySection(emailVerified: true, onChanged: () {})),
    ));
    expect(find.textContaining('Tu correo no está verificado'), findsNothing);
  });

  testWidgets('la verificación muestra el error y acepta el código correcto', (tester) async {
    final service = _FakeAccountService();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: EmailVerificationSheet(service: service))));

    await tester.enterText(find.byType(TextField), '000000');
    await tester.tap(find.text('Verificar'));
    await tester.pump();
    expect(find.text('El código no es correcto.'), findsOneWidget);

    await tester.enterText(find.byType(TextField), '123456');
    await tester.tap(find.text('Verificar'));
    await tester.pump();
    expect(service.confirmed, '123456');
  });

  test('el error de la API conserva su código', () {
    const error = ApiException('Verifica tu correo', statusCode: 403, code: 'correo_no_verificado');
    expect(error.code, 'correo_no_verificado');
  });
}
