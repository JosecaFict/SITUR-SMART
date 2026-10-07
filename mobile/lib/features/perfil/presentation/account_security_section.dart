import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../favoritos/data/favorites_store.dart';
import '../../notificaciones/data/notifications_store.dart';
import '../data/account_service.dart';
import 'email_verification_sheet.dart';

/// "Seguridad" en Mi Perfil: verificar el correo, cambiar la contraseña, ver y
/// cerrar sesiones y eliminar la cuenta.
class AccountSecuritySection extends StatelessWidget {
  const AccountSecuritySection({super.key, required this.emailVerified, required this.onChanged, this.service});

  final bool emailVerified;

  /// Algo cambió (correo verificado): Mi Perfil vuelve a cargar.
  final VoidCallback onChanged;
  final AccountService? service;

  AccountService get _service => service ?? AccountService();

  void _toast(BuildContext context, String text) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));

  Future<void> _verify(BuildContext context) async {
    if (await showEmailVerificationSheet(context, service: _service, sendFirst: true)) {
      onChanged();
      if (context.mounted) _toast(context, 'Correo verificado. Ya puedes reservar.');
    }
  }

  Future<void> _changePassword(BuildContext context) async {
    final changed = await showDialog<bool>(context: context, builder: (_) => _ChangePasswordDialog(service: _service));
    if (changed == true && context.mounted) {
      _toast(context, 'Contraseña cambiada. Cerramos tus sesiones en los demás dispositivos.');
    }
  }

  Future<void> _sessions(BuildContext context) => showModalBottomSheet<void>(
        context: context,
        showDragHandle: true,
        isScrollControlled: true,
        builder: (_) => _SessionsSheet(service: _service),
      );

  Future<void> _delete(BuildContext context) async {
    final deleted = await showDialog<bool>(context: context, builder: (_) => _DeleteAccountDialog(service: _service));
    if (deleted == true && context.mounted) {
      FavoritesStore.instance.clear();
      NotificationsStore.instance.clear();
      context.go('/login');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('Seguridad', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        if (!emailVerified)
          Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFFFFFBEB),
              border: Border.all(color: const Color(0xFFFDE68A)),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              children: [
                const Icon(Icons.mark_email_unread_outlined, color: Color(0xFFB45309)),
                const SizedBox(width: 10),
                const Expanded(child: Text('Tu correo no está verificado. Lo necesitas para reservar.')),
                TextButton(onPressed: () => _verify(context), child: const Text('Verificar')),
              ],
            ),
          ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.lock_outline, color: AppTheme.accentDark),
          title: const Text('Cambiar contraseña'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => _changePassword(context),
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.devices_outlined, color: AppTheme.accentDark),
          title: const Text('Sesiones abiertas'),
          subtitle: const Text('Dónde tienes la cuenta iniciada'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => _sessions(context),
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: Icon(Icons.delete_outline, color: Theme.of(context).colorScheme.error),
          title: Text('Eliminar mi cuenta', style: TextStyle(color: Theme.of(context).colorScheme.error)),
          onTap: () => _delete(context),
        ),
      ],
    );
  }
}

class _ChangePasswordDialog extends StatefulWidget {
  const _ChangePasswordDialog({required this.service});

  final AccountService service;

  @override
  State<_ChangePasswordDialog> createState() => _ChangePasswordDialogState();
}

class _ChangePasswordDialogState extends State<_ChangePasswordDialog> {
  final _current = TextEditingController();
  final _next = TextEditingController();
  bool _working = false;
  String? _error;

  @override
  void dispose() {
    _current.dispose();
    _next.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_next.text.length < 8) {
      setState(() => _error = 'La contraseña nueva debe tener al menos 8 caracteres.');
      return;
    }
    setState(() {
      _working = true;
      _error = null;
    });
    try {
      await widget.service.changePassword(current: _current.text, next: _next.text);
      if (mounted) Navigator.of(context).pop(true);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _working = false;
        _error = error is ApiException ? error.message : 'No se pudo cambiar la contraseña.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Cambiar contraseña'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(controller: _current, obscureText: true, decoration: const InputDecoration(labelText: 'Contraseña actual')),
          const SizedBox(height: 8),
          TextField(controller: _next, obscureText: true, decoration: const InputDecoration(labelText: 'Contraseña nueva')),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ],
        ],
      ),
      actions: [
        TextButton(onPressed: _working ? null : () => Navigator.pop(context, false), child: const Text('Cancelar')),
        TextButton(onPressed: _working ? null : _save, child: const Text('Guardar')),
      ],
    );
  }
}

class _SessionsSheet extends StatefulWidget {
  const _SessionsSheet({required this.service});

  final AccountService service;

  @override
  State<_SessionsSheet> createState() => _SessionsSheetState();
}

class _SessionsSheetState extends State<_SessionsSheet> {
  static final DateFormat _format = DateFormat('d MMM yyyy, HH:mm', 'es');

  List<AccountSession>? _sessions;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final sessions = await widget.service.sessions();
      if (mounted) setState(() => _sessions = sessions);
    } catch (error) {
      if (mounted) setState(() => _error = error is ApiException ? error.message : 'No se pudieron cargar las sesiones.');
    }
  }

  Future<void> _run(Future<void> Function() action) async {
    try {
      await action();
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = error is ApiException ? error.message : 'No se pudo cerrar la sesión.');
    }
  }

  @override
  Widget build(BuildContext context) {
    final sessions = _sessions;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Sesiones abiertas', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            if (sessions == null && _error == null)
              const Padding(padding: EdgeInsets.all(20), child: Center(child: CircularProgressIndicator())),
            if (sessions != null)
              Flexible(
                child: ListView(
                  shrinkWrap: true,
                  children: [
                    for (final session in sessions)
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(session.current ? Icons.smartphone : Icons.devices_other),
                        title: Text(session.current ? 'Este dispositivo' : session.device, maxLines: 1, overflow: TextOverflow.ellipsis),
                        subtitle: Text('Desde el ${_format.format(session.startedAt)}'),
                        trailing: session.current
                            ? null
                            : TextButton(
                                onPressed: () => _run(() => widget.service.closeSession(session.id)),
                                child: const Text('Cerrar'),
                              ),
                      ),
                  ],
                ),
              ),
            if (sessions != null && sessions.where((s) => !s.current).isNotEmpty)
              OutlinedButton(
                onPressed: () => _run(() => widget.service.closeOtherSessions().then((_) {})),
                child: const Text('Cerrar todas las demás'),
              ),
          ],
        ),
      ),
    );
  }
}

class _DeleteAccountDialog extends StatefulWidget {
  const _DeleteAccountDialog({required this.service});

  final AccountService service;

  @override
  State<_DeleteAccountDialog> createState() => _DeleteAccountDialogState();
}

class _DeleteAccountDialogState extends State<_DeleteAccountDialog> {
  final _password = TextEditingController();
  bool _working = false;
  String? _error;

  @override
  void dispose() {
    _password.dispose();
    super.dispose();
  }

  Future<void> _delete() async {
    setState(() {
      _working = true;
      _error = null;
    });
    try {
      await widget.service.deleteAccount(_password.text);
      if (mounted) Navigator.of(context).pop(true);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _working = false;
        _error = error is ApiException ? error.message : 'No se pudo eliminar la cuenta.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Eliminar mi cuenta'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Se borran tu nombre, correo y teléfono, y tus reservas sin pagar se cancelan. '
            'Las reservas ya pagadas se mantienen para la empresa. No se puede deshacer.',
          ),
          const SizedBox(height: 12),
          TextField(controller: _password, obscureText: true, decoration: const InputDecoration(labelText: 'Tu contraseña')),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ],
        ],
      ),
      actions: [
        TextButton(onPressed: _working ? null : () => Navigator.pop(context, false), child: const Text('Cancelar')),
        TextButton(
          onPressed: _working ? null : _delete,
          child: Text('Eliminar', style: TextStyle(color: Theme.of(context).colorScheme.error)),
        ),
      ],
    );
  }
}
