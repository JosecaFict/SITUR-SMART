import 'package:flutter/material.dart';

import '../data/role_service.dart';
import '../models/role.dart';

import '../../../core/theme/app_theme.dart';


/// Pantalla de gestión de roles.
///
/// Obtiene la información desde backend mediante
/// RoleService y muestra los roles registrados.
class RolesPage extends StatefulWidget {

  const RolesPage({
    super.key,
  });


  @override
  State<RolesPage> createState() =>
      _RolesPageState();

}



/// Controla la carga de roles desde la API.
class _RolesPageState extends State<RolesPage> {


  final RoleService _roleService =
      RoleService();


  List<Role> _roles = [];


  bool _loading = true;


  String? _error;



  @override
  void initState() {

    super.initState();

    _loadRoles();

  }



  /// Obtiene los roles reales desde backend.
  Future<void> _loadRoles() async {

    try {

      final roles =
          await _roleService.getRoles();


      setState(() {

        _roles = roles;

        _loading = false;

      });


    } catch (e) {

      setState(() {

        _error = e.toString();

        _loading = false;

      });

    }

  }



  @override
  Widget build(BuildContext context) {


    if (_loading) {

      return const Center(

        child:
            CircularProgressIndicator(),

      );

    }



    if (_error != null) {

      return Center(

        child:
            Text(
              _error!,
            ),

      );

    }



    return RefreshIndicator(

      onRefresh:
          _loadRoles,


      child:
          ListView(

        padding:
            const EdgeInsets.all(20),


        children: [


          const Text(

            'Roles y permisos',

            style:
                TextStyle(

              fontSize:
                  28,

              fontWeight:
                  FontWeight.bold,

              color:
                  AppTheme.titleColor,

            ),

          ),



          const SizedBox(
            height: 8,
          ),



          const Text(

            'Administración de accesos del sistema',

            style:
                TextStyle(

              color:
                  AppTheme.textSecondary,

            ),

          ),



          const SizedBox(
            height: 20,
          ),



          ..._roles.map(

            (role) => _RoleCard(

              role:
                  role,

            ),

          ),


        ],

      ),

    );

  }

}





/// Tarjeta visual de un rol.
class _RoleCard extends StatelessWidget {


  final Role role;



  const _RoleCard({

    required this.role,

  });



  @override
  Widget build(BuildContext context) {


    return Container(

      margin:
          const EdgeInsets.only(
            bottom: 14,
          ),


      padding:
          const EdgeInsets.all(18),


      decoration:
          BoxDecoration(

        color:
            Colors.white,

        borderRadius:
            BorderRadius.circular(18),


        border:
            Border.all(

              color:
                  AppTheme.demoBorder,

            ),

      ),



      child:
          Column(

        crossAxisAlignment:
            CrossAxisAlignment.start,


        children: [


          Row(

            children: [


              Container(

                padding:
                    const EdgeInsets.all(10),


                decoration:
                    BoxDecoration(

                  color:
                      AppTheme.demoBg,


                  borderRadius:
                      BorderRadius.circular(12),

                ),


                child:
                    const Icon(

                  Icons.security,

                  color:
                      AppTheme.accentDark,

                ),

              ),



              const SizedBox(
                width: 12,
              ),



              Expanded(

                child:
                    Text(

                  role.codigo,

                  style:
                      const TextStyle(

                    fontSize:
                        17,

                    fontWeight:
                        FontWeight.bold,

                  ),

                ),

              ),



            ],

          ),



          const SizedBox(
            height: 12,
          ),



          Text(

            role.nombre,

            style:
                const TextStyle(

              fontSize:
                  15,

            ),

          ),



          const SizedBox(
            height: 8,
          ),



          Row(

            children: [


              const Icon(

                Icons.public,

                size:
                    16,

                color:
                    AppTheme.accentDark,

              ),


              const SizedBox(
                width: 6,
              ),


              Text(

                role.ambito,

                style:
                    const TextStyle(

                  color:
                      AppTheme.accentDark,

                  fontWeight:
                      FontWeight.bold,

                ),

              ),


              const SizedBox(
                width: 15,
              ),



              if (role.esSistema)

                const Text(

                  'Sistema',

                  style:
                      TextStyle(

                    color:
                        AppTheme.accentDark,

                    fontWeight:
                        FontWeight.bold,

                  ),

                ),


            ],

          ),



          if (role.permisos.isNotEmpty) ...[


            const SizedBox(
              height: 12,
            ),


            const Text(

              'Permisos',

              style:
                  TextStyle(

                fontWeight:
                    FontWeight.bold,

              ),

            ),



            ...role.permisos.map(

              (permiso) => Text(

                '• $permiso',

              ),

            ),


          ],



        ],

      ),


    );

  }


}