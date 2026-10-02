import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';


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

              Icons.explore_outlined,

              'Explorar',

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





            Container(

              margin:
                  const EdgeInsets.all(16),


              padding:
                  const EdgeInsets.all(12),


              decoration:

                  BoxDecoration(

                color:
                    Colors.black12,

                borderRadius:

                    BorderRadius.circular(14),

              ),



              child:

                  const Row(

                children: [



                  CircleAvatar(

                    backgroundColor:

                        AppTheme.accent,

                    child:

                        Icon(

                      Icons.person,

                      color:
                          Colors.white,

                    ),

                  ),



                  SizedBox(

                    width:12,

                  ),



                  Expanded(

                    child:

                        Column(

                      crossAxisAlignment:

                          CrossAxisAlignment.start,

                      children: [



                        Text(

                          'Administrador',

                          style:

                              TextStyle(

                            color:
                                Colors.white,

                            fontWeight:

                                FontWeight.bold,

                          ),

                        ),



                        Text(

                          'SUPER_ADMIN',

                          style:

                              TextStyle(

                            color:

                                Colors.white70,

                          ),

                        ),


                      ],

                    ),

                  ),


                ],

              ),

            ),



          ],

        ),

      ),

    );

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