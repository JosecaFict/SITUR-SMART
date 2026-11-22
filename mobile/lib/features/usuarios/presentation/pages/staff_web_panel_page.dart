import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../notificaciones/data/notifications_store.dart';
import '../../../notificaciones/presentation/notification_bell.dart';
import '../../data/auth_service.dart';

/// Lo que ve el personal de una empresa o el SuperAdmin si entra a la app.
///
/// El personal recibe comunicaciones en la app. La administración (empresas, catálogo,
/// clientes, reportes, copias de seguridad) se hace solo desde el panel web,
/// así hay un único lugar de control.
class StaffWebPanelPage extends StatefulWidget {
  const StaffWebPanelPage({super.key});

  static const String webUrl = String.fromEnvironment(
    'WEB_URL',
    defaultValue: 'https://situr-smart-web.vercel.app',
  );

  @override
  State<StaffWebPanelPage> createState() => _StaffWebPanelPageState();
}

class _StaffWebPanelPageState extends State<StaffWebPanelPage>
    with WidgetsBindingObserver {
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    NotificationsStore.instance.refresh();
    _poll = Timer.periodic(
      const Duration(minutes: 1),
      (_) => NotificationsStore.instance.refresh(),
    );
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      NotificationsStore.instance.refresh();
    }
  }

  @override
  void dispose() {
    _poll?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  Future<void> _openPanel(BuildContext context) async {
    final opened = await launchUrl(
      Uri.parse('${StaffWebPanelPage.webUrl}/login'),
      mode: LaunchMode.externalApplication,
    );
    if (!opened && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'No se pudo abrir el navegador. Entra a ${StaffWebPanelPage.webUrl}',
          ),
        ),
      );
    }
  }

  Future<void> _logout(BuildContext context) async {
    await AuthService().logout();
    if (context.mounted) context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.accentDark,
      appBar: AppBar(
        title: const Text('Mi cuenta'),
        actions: const [NotificationBell()],
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(28),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Image(
                  image: AssetImage('assets/branding/logo-oscuro.png'),
                  height: 56,
                ),
                const SizedBox(height: 32),
                const Icon(
                  Icons.desktop_windows_outlined,
                  color: Colors.white,
                  size: 48,
                ),
                const SizedBox(height: 16),
                const Text(
                  'La administración se hace desde el panel web',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 12),
                const Text(
                  'Recibe y lee tus comunicaciones desde la bandeja de esta app. '
                  'Gestiona tu catálogo, reservas, clientes y reportes desde el navegador.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.white70, height: 1.5),
                ),
                const SizedBox(height: 28),
                ElevatedButton.icon(
                  onPressed: () async {
                    await context.push('/notificaciones');
                    NotificationsStore.instance.refresh();
                  },
                  icon: const Icon(Icons.mail_outline),
                  label: const Text('Ver comunicaciones y avisos'),
                ),
                const SizedBox(height: 12),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.white,
                    foregroundColor: AppTheme.accentDark,
                  ),
                  onPressed: () => _openPanel(context),
                  icon: const Icon(Icons.open_in_new),
                  label: const Text('Abrir el panel web'),
                ),
                const SizedBox(height: 12),
                TextButton(
                  onPressed: () => _logout(context),
                  child: const Text(
                    'Cerrar sesión',
                    style: TextStyle(color: Colors.white),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
