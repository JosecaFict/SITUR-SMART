import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';

import '../../../tenants/data/tenant_service.dart';
import '../../../tenants/models/tenant.dart';
import '../../../tenants/presentation/tenant_form_page.dart';



class HomePage extends StatefulWidget {

  const HomePage({
    super.key,
  });


  @override
  State<HomePage> createState() => _HomePageState();

}




class _HomePageState extends State<HomePage> {


  final TenantService _tenantService = TenantService();


  List<Tenant> _tenants = [];

  bool _loading = true;

  String? _error;



  @override
  void initState() {

    super.initState();

    _loadTenants();

  }




  Future<void> _loadTenants() async {

    try {


      final tenants = await _tenantService.getTenants();


      setState(() {

        _tenants = tenants;

        _loading = false;

      });


    } catch(e) {


      setState(() {

        _error = e.toString();

        _loading = false;

      });


    }

  }






  Future<void> _openCreateTenant() async {


    final created = await Navigator.push(

      context,

      MaterialPageRoute(

        builder: (_) => const TenantFormPage(),

      ),

    );



    if(created == true){


      setState(() {

        _loading = true;

      });


      _loadTenants();


    }


  }







  @override
  Widget build(BuildContext context) {


    return Scaffold(


      appBar: AppBar(


        title: const Text(
          'SITUR-SMART',
        ),



        actions: [



          IconButton(

            onPressed: _openCreateTenant,

            icon: const Icon(
              Icons.add_business,
            ),

          ),

		  IconButton(
  onPressed: (){
    context.go('/users');
  },
  icon: const Icon(
    Icons.people,
  ),
),



          TextButton.icon(


            onPressed: () {


              context.go('/login');


            },


            icon: const Icon(

              Icons.logout,

              size: 18,

            ),



            label: const Text(

              'Salir',

            ),


          ),



        ],


      ),





      body: _buildBody(),



    );


  }







  Widget _buildBody(){



    if(_loading){


      return const Center(

        child: CircularProgressIndicator(),

      );


    }






    if(_error != null){


      return Center(

        child: Text(

          _error!,

        ),

      );


    }







    return ListView.builder(



      padding: const EdgeInsets.all(20),



      itemCount: _tenants.length,





      itemBuilder: (context,index){



        final tenant = _tenants[index];





        return Card(



          margin: const EdgeInsets.only(

            bottom: 12,

          ),





          child: ListTile(




            leading: const Icon(

              Icons.business,

              color: AppTheme.accentDark,

            ),






            title: Text(

              tenant.nombreComercial,

            ),





            subtitle: Text(

              tenant.razonSocial,

            ),





            trailing: const Icon(

              Icons.arrow_forward_ios,

              size: 16,

            ),






            onTap: (){



              showDialog(



                context: context,



                builder: (_) => AlertDialog(



                  title: Text(

                    tenant.nombreComercial,

                  ),




                  content: const Text(

                    'Próximamente',

                  ),





                  actions: [



                    TextButton(



                      onPressed: (){


                        Navigator.pop(context);


                      },



                      child: const Text(

                        'Cerrar',

                      ),



                    ),



                  ],



                ),



              );



            },




          ),



        );



      },



    );



  }



}