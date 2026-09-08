import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';


/// Barra superior principal del sistema.
///
/// Muestra la identidad de SITUR-SMART
/// y permite abrir el menú lateral Drawer.
class SiturAppBar extends StatelessWidget
    implements PreferredSizeWidget {

  final String title;


  const SiturAppBar({
    super.key,
    required this.title,
  });



  @override
  Widget build(BuildContext context) {

    return AppBar(

      backgroundColor:
          AppTheme.accentDark,


      foregroundColor:
          Colors.white,


      elevation:
          0,


      centerTitle:
          false,


      titleSpacing:
          0,


      title:
          Row(

        children: [


          Container(

            padding:
                const EdgeInsets.all(6),


            decoration:
                BoxDecoration(

              color:
                  Colors.white24,

              borderRadius:
                  BorderRadius.circular(10),

            ),


            child:
                const Icon(

              Icons.travel_explore,

              color:
                  Colors.white,

              size:
                  26,

            ),

          ),


          const SizedBox(
            width: 12,
          ),



          Text(

            title,

            style:
                const TextStyle(

              fontWeight:
                  FontWeight.bold,

              fontSize:
                  20,

            ),

          ),

        ],

      ),

    );

  }



  @override
  Size get preferredSize =>
      const Size.fromHeight(
        kToolbarHeight,
      );

}