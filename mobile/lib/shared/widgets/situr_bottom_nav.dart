import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';


/// Barra de navegación inferior principal.
///
/// Permite cambiar entre los módulos principales
/// del sistema SITUR-SMART.
class SiturBottomNav extends StatelessWidget {

  final int currentIndex;

  final Function(int) onTap;


  const SiturBottomNav({
    super.key,
    required this.currentIndex,
    required this.onTap,
  });



  @override
  Widget build(BuildContext context) {


    return NavigationBarTheme(

      data:
          NavigationBarThemeData(

        backgroundColor:
            Colors.white,


        indicatorColor:
            AppTheme.demoBorder,


        labelTextStyle:
            WidgetStateProperty.resolveWith(

          (states) {

            if (states.contains(
              WidgetState.selected,
            )) {

              return const TextStyle(

                color:
                    AppTheme.accentDark,

                fontWeight:
                    FontWeight.bold,

              );

            }


            return const TextStyle(

              color:
                  AppTheme.textSecondary,

            );

          },

        ),

      ),



      child:
          NavigationBar(

        height:
            72,


        elevation:
            8,


        selectedIndex:
            currentIndex,


        onDestinationSelected:
            onTap,


        destinations: const [


          NavigationDestination(

            icon:
                Icon(
                  Icons.dashboard_outlined,
                ),

            selectedIcon:
                Icon(
                  Icons.dashboard,
                  color: AppTheme.accentDark,
                ),

            label:
                'Inicio',

          ),



          NavigationDestination(

            icon:
                Icon(
                  Icons.people_outline,
                ),

            selectedIcon:
                Icon(
                  Icons.people,
                  color: AppTheme.accentDark,
                ),

            label:
                'Usuarios',

          ),



          NavigationDestination(

            icon:
                Icon(
                  Icons.security_outlined,
                ),

            selectedIcon:
                Icon(
                  Icons.security,
                  color: AppTheme.accentDark,
                ),

            label:
                'Roles',

          ),



          NavigationDestination(

            icon:
                Icon(
                  Icons.history_outlined,
                ),

            selectedIcon:
                Icon(
                  Icons.history,
                  color: AppTheme.accentDark,
                ),

            label:
                'Bitácora',

          ),

        ],

      ),

    );

  }

}