import 'package:flutter/material.dart';

import '../../../core/network/api_client.dart';
import '../data/account_service.dart';

/// Pide el código de 6 dígitos que llegó al correo. Devuelve true si quedó
/// verificado. Para reservar hace falta el correo verificado.
Future<bool> showEmailVerificationSheet(BuildContext context, {AccountService? service, bool sendFirst = false}) async {
  final verified = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => EmailVerificationSheet(service: service, sendFirst: sendFirst),
  );
  return verified == true;
}

class EmailVerificationSheet extends StatefulWidget {
  const EmailVerificationSheet({super.key, this.service, this.sendFirst = false});

  final AccountService? service;

  /// Manda un código nuevo al abrir (si el de registro ya se perdió).
  final bool sendFirst;

  @override
  State<EmailVerificationSheet> createState() => _EmailVerificationSheetState();
}

class _EmailVerificationSheetState extends State<EmailVerificationSheet> {
  late final AccountService _service = widget.service ?? AccountService();
  final _code = TextEditingController();
  bool _working = false;
  String? _error;
  String? _info;

  @override
  void initState() {
    super.initState();
    if (widget.sendFirst) _resend();
  }

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _resend() async {
    setState(() {
      _error = null;
      _info = null;
    });
    try {
      await _service.sendEmailCode();
      if (mounted) setState(() => _info = 'Te enviamos un código nuevo. Revisa tu correo (y la carpeta de spam).');
    } catch (error) {
      if (mounted) setState(() => _error = error is ApiException ? error.message : 'No se pudo enviar el código.');
    }
  }

  Future<void> _confirm() async {
    if (_code.text.trim().length != 6 || _working) {
      setState(() => _error = 'El código tiene 6 dígitos.');
      return;
    }
    setState(() {
      _working = true;
      _error = null;
    });
    try {
      await _service.confirmEmail(_code.text);
      if (mounted) Navigator.of(context).pop(true);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _working = false;
        _error = error is ApiException ? error.message : 'No se pudo verificar el código.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Verifica tu correo', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          const Text('Para reservar necesitamos confirmar tu correo. Escribe el código de 6 dígitos que te enviamos.'),
          const SizedBox(height: 16),
          TextField(
            controller: _code,
            keyboardType: TextInputType.number,
            maxLength: 6,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 24, letterSpacing: 8, fontWeight: FontWeight.w700),
            decoration: const InputDecoration(labelText: 'Código', counterText: ''),
            onSubmitted: (_) => _confirm(),
          ),
          if (_info != null) ...[const SizedBox(height: 8), Text(_info!)],
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ],
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: _working ? null : _confirm,
            child: _working
                ? const SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Verificar'),
          ),
          TextButton(onPressed: _working ? null : _resend, child: const Text('Reenviar el código')),
        ],
      ),
    );
  }
}
