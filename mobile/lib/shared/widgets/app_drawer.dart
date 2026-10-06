import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/storage/token_storage.dart';
import '../../core/theme/app_theme.dart';
import '../../features/usuarios/data/auth_service.dart';


class AppDrawer extends StatelessWidget {


  final Function(int) onSelect;


  const AppDrawer({

    super.key,

    required this.onSelect,

  });



  @override
  Widget build(BuildContext context) {


    return Drawer(

      backgroundColor:
          AppTheme.accentDark,


      child: SafeArea(

        child: Column(

          children: [


            Padding(

              padding:
                  const EdgeInsets.all(20),

              child: Row(

                children: [


                  const Expanded(

                    child: Text(

                      'SITUR-SMART',

                      style: TextStyle(

                        color: Colors.white,

                        fontSize: 22,

                        fontWeight:
                            FontWeight.bold,

                      ),

                    ),

                  ),



                  IconButton(

                    icon: const Icon(

                      Icons.close,

                      color: Colors.white,

                    ),

                    onPressed: () {

                      Navigator.pop(context);

                    },

                  ),

                ],

              ),

            ),




            _item(

              context,

              Icons.dashboard_outlined,

              'Dashboard',

              0,

            ),



            _item(

              context,

              Icons.people_outline,

              'Usuarios',

              1,

            ),



            _item(

              context,

              Icons.person_outline,

              'Mi Perfil',

              2,

            ),



            _item(

              context,

              Icons.business_outlined,

              'Empresas',

              3,

            ),



            _item(

              context,

              Icons.security_outlined,

              'Roles y permisos',

              4,

            ),



            _item(

              context,

              Icons.inventory_2_outlined,

              'Catálogo',

              5,

            ),



            _item(

              context,

              Icons.history,

              'Bitácora',

              6,

            ),




            const Spacer(),

            ListTile(
              leading: const Icon(Icons.logout, color: Colors.white),
              title: const Text(
                'Cerrar sesión',
                style: TextStyle(color: Colors.white, fontSize: 16),
              ),
              onTap: () => _logout(context),
            ),

            const _UserCard(),
          ],
        ),
      ),
    );
  }

  Future<void> _logout(BuildContext context) async {
    final router = GoRouter.of(context);
    Navigator.pop(context);
    await AuthService().logout();
    router.go('/login');
  }

  Widget _item(

    BuildContext context,

    IconData icon,

    String texto,

    int index,

  ){


    return ListTile(


      leading:

          Icon(

        icon,

        color:
            Colors.white,

      ),



      title:

          Text(

        texto,

        style:

            const TextStyle(

          color:
              Colors.white,

          fontSize: 16,

        ),

      ),



      onTap: () {


        Navigator.pop(context);


        onSelect(index);


      },


    );

  }


}


/// Usuario de la sesión actual, leído del almacenamiento local.
class _UserCard extends StatelessWidget {
  const _UserCard();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>?>(
      future: TokenStorage().getUser(),
      builder: (context, snapshot) {
        final user = snapshot.data;
        final name = '${user?['nombres'] ?? ''} ${user?['apellidos'] ?? ''}'.trim();
        final roles = user?['roles'];
        final tenants = user?['tenants'];
        final subtitle = [
          if (roles is List && roles.isNotEmpty) roles.join(', '),
          if (tenants is List && tenants.isNotEmpty) tenants.first['name'],
        ].join(' · ');
        return Container(
          margin: const EdgeInsets.all(16),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.black12,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Row(
            children: [
              const CircleAvatar(
                backgroundColor: AppTheme.accent,
                child: Icon(Icons.person, color: Colors.white),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name.isEmpty ? (user?['email'] ?? '') : name,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                    ),
                    if (subtitle.isNotEmpty)
                      Text(
                        subtitle,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: Colors.white70),
                      ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
