import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme/app_theme.dart';
import '../notificaciones/data/notifications_store.dart';

/// Navegación principal del turista: Explorar, Favoritos, Viajes, Asistente y
/// Mi Perfil.
///
/// Cada pestaña es una rama de StatefulShellRoute, así que al cambiar de
/// pestaña no se pierde la búsqueda ni la conversación en curso.
///
/// Mientras la app está abierta, el contador de notificaciones se pone al día
/// cada minuto y al volver a la app. El push de Firebase lo actualiza al
/// instante; esta consulta queda como respaldo si el push no llega.
class TouristShellPage extends StatefulWidget {
  const TouristShellPage({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  State<TouristShellPage> createState() => _TouristShellPageState();
}

class _TouristShellPageState extends State<TouristShellPage> with WidgetsBindingObserver {
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    NotificationsStore.instance.refresh();
    _poll = Timer.periodic(const Duration(minutes: 1), (_) => NotificationsStore.instance.refresh());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _poll?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) NotificationsStore.instance.refresh();
  }

  @override
  Widget build(BuildContext context) {
    final shell = widget.navigationShell;
    return Scaffold(
      body: shell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: shell.currentIndex,
        indicatorColor: AppTheme.demoBorder,
        backgroundColor: Colors.white,
        onDestinationSelected: (index) => shell.goBranch(
          index,
          // Tocar la pestaña activa la devuelve a su inicio.
          initialLocation: index == shell.currentIndex,
        ),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.travel_explore_outlined),
            selectedIcon: Icon(Icons.travel_explore),
            label: 'Explorar',
          ),
          NavigationDestination(
            icon: Icon(Icons.favorite_border),
            selectedIcon: Icon(Icons.favorite),
            label: 'Favoritos',
          ),
          NavigationDestination(
            icon: Icon(Icons.luggage_outlined),
            selectedIcon: Icon(Icons.luggage),
            label: 'Viajes',
          ),
          NavigationDestination(
            icon: Icon(Icons.smart_toy_outlined),
            selectedIcon: Icon(Icons.smart_toy),
            label: 'Asistente',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person),
            label: 'Mi Perfil',
          ),
        ],
      ),
    );
  }
}
