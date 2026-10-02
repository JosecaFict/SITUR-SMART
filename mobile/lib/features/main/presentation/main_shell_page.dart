import 'package:flutter/material.dart';

import '../../usuarios/presentation/pages/users_page.dart';
import '../../dashboard/presentation/dashboard_page.dart';
import '../../roles/presentation/roles_page.dart';
import '../../bitacora/presentation/bitacora_page.dart';

import '../../../shared/widgets/situr_app_bar.dart';
import '../../../shared/widgets/situr_bottom_nav.dart';
import '../../../shared/widgets/app_drawer.dart';



class MainShellPage extends StatefulWidget {

  const MainShellPage({
    super.key,
  });


  @override
  State<MainShellPage> createState() =>
      _MainShellPageState();

}





class _MainShellPageState extends State<MainShellPage> {


  int _currentIndex = 0;



  final List<Widget> _pages = [


    const DashboardPage(),


    const UsersPage(),



    const _SimplePage(

      title: "Mi Perfil",

      icon: Icons.person,

    ),



    const _SimplePage(

      title: "Empresas",

      icon: Icons.business,

    ),



    const RolesPage(),



    const _SimplePage(

      title: "Catálogo",

      icon: Icons.inventory_2,

    ),



    const BitacoraPage(),


  ];






  @override
  Widget build(BuildContext context) {


    return Scaffold(



      drawer:

          AppDrawer(

        onSelect: (index) {


          setState(() {

            _currentIndex = index;

          });


        },

      ),




      appBar:

          SiturAppBar(

        title:

            'SITUR-SMART',

      ),




      body:

          _pages[_currentIndex],





      bottomNavigationBar:

          SiturBottomNav(

        currentIndex:

            _bottomIndex(),



        onTap:

            (index) {


          int pageIndex;



          switch(index){



            case 0:

              pageIndex = 0;

              break;



            case 1:

              pageIndex = 1;

              break;



            case 2:

              pageIndex = 4;

              break;



            case 3:

              pageIndex = 6;

              break;



            default:

              pageIndex = 0;

          }




          setState(() {


            _currentIndex = pageIndex;


          });


        },

      ),


    );


  }







  int _bottomIndex(){


    switch(_currentIndex){


      case 0:

        return 0;



      case 1:

        return 1;



      case 4:

        return 2;



      case 6:

        return 3;



      default:

        return 0;

    }


  }


}








class _SimplePage extends StatelessWidget {


  final String title;

  final IconData icon;



  const _SimplePage({

    required this.title,

    required this.icon,

  });





  @override
  Widget build(BuildContext context) {


    return Center(


      child: Column(


        mainAxisAlignment:

            MainAxisAlignment.center,



        children: [



          Icon(

            icon,

            size:

                60,

            color:

                Colors.grey,

          ),




          const SizedBox(

            height:

                15,

          ),




          Text(

            title,

            style:

                const TextStyle(

              fontSize:

                  24,

              fontWeight:

                  FontWeight.bold,

            ),

          ),



        ],


      ),


    );


  }

}