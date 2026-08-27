import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme/app_theme.dart';


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

      backgroundColor: AppTheme.accentDark,

      foregroundColor: Colors.white,

      elevation: 0,

      title: Text(
        title,
        style: const TextStyle(
          fontWeight: FontWeight.bold,
        ),
      ),


      actions: [

        IconButton(

          icon: const Icon(
            Icons.logout,
          ),

          onPressed: () {

            context.go('/login');

          },

        ),

      ],

    );

  }



  @override
  Size get preferredSize =>
      const Size.fromHeight(kToolbarHeight);

}