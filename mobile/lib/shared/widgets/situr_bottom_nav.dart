import 'package:flutter/material.dart';


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


    return NavigationBar(

      selectedIndex: currentIndex,


      onDestinationSelected: onTap,


      destinations: const [

        NavigationDestination(

          icon: Icon(Icons.business),

          label: 'Dashboard',

        ),


        NavigationDestination(

          icon: Icon(Icons.people),

          label: 'Usuarios',

        ),


        NavigationDestination(

          icon: Icon(Icons.security),

          label: 'Roles',

        ),


        NavigationDestination(

          icon: Icon(Icons.history),

          label: 'Bitácora',

        ),

      ],

    );


  }


}