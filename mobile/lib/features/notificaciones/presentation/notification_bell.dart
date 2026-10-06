import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../data/notifications_store.dart';

/// Campana con el número de avisos sin leer. Abre la bandeja.
class NotificationBell extends StatelessWidget {
  const NotificationBell({super.key, this.store});

  final NotificationsStore? store;

  @override
  Widget build(BuildContext context) {
    final store = this.store ?? NotificationsStore.instance;
    return ListenableBuilder(
      listenable: store,
      builder: (context, _) {
        final unread = store.unread;
        return IconButton(
          tooltip: unread == 0 ? 'Notificaciones' : 'Notificaciones, $unread sin leer',
          onPressed: () async {
            await context.push('/notificaciones');
            store.refresh();
          },
          icon: Badge(
            isLabelVisible: unread > 0,
            label: Text(unread > 9 ? '9+' : '$unread'),
            child: Icon(unread > 0 ? Icons.notifications : Icons.notifications_none),
          ),
        );
      },
    );
  }
}
