import 'package:flutter/material.dart';

import '../../usuarios/presentation/pages/users_page.dart';

import '../../dashboard/presentation/dashboard_page.dart';

import '../../roles/presentation/roles_page.dart';

import '../../bitacora/presentation/bitacora_page.dart';

import '../../../shared/widgets/situr_app_bar.dart';
import '../../../shared/widgets/situr_bottom_nav.dart';


class MainShellPage extends StatefulWidget {

  const MainShellPage({
    super.key,
  });


  @override
  State<MainShellPage> createState() =>
      _MainShellPageState();

}




class _MainShellPageState
    extends State<MainShellPage> {


  int _currentIndex = 0;



  final List<Widget> _pages = [

    const DashboardPage(),

    const UsersPage(),

    const RolesPage(),

    const BitacoraPage(),

  ];





  @override
  Widget build(BuildContext context) {


    return Scaffold(


      appBar: SiturAppBar(

        title: 'SITUR-SMART',

      ),



      body: _pages[_currentIndex],



      bottomNavigationBar: SiturBottomNav(

        currentIndex: _currentIndex,

        onTap: (index){

          setState(() {

            _currentIndex = index;

          });

        },

      ),


    );


  }



}