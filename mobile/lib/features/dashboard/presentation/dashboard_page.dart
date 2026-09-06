import 'package:flutter/material.dart';

import '../../tenants/data/tenant_service.dart';
import '../../tenants/models/tenant.dart';

import '../../../core/theme/app_theme.dart';


class DashboardPage extends StatefulWidget {

  const DashboardPage({
    super.key,
  });


  @override
  State<DashboardPage> createState() =>
      _DashboardPageState();

}



class _DashboardPageState extends State<DashboardPage> {


  final TenantService _tenantService =
      TenantService();


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

      final tenants =
          await _tenantService.getTenants();


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





  @override
  Widget build(BuildContext context) {


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



    return RefreshIndicator(

      onRefresh: _loadTenants,


      child: ListView(

        padding: const EdgeInsets.all(20),


        children: [



          const Text(

            'Bienvenido, Alex Lupa',

            style: TextStyle(

              fontSize: 22,

              fontWeight: FontWeight.bold,

              color: AppTheme.titleColor,

            ),

          ),

          const SizedBox(height: 28),

          const Text(

            'Empresas registradas',

            style: TextStyle(

              fontSize: 20,

              fontWeight: FontWeight.bold,

            ),

          ),



          const SizedBox(height: 16),




          ..._tenants.map((tenant){


            return Container(


              margin: const EdgeInsets.only(
                bottom: 14,
              ),



              decoration: BoxDecoration(

                color: const Color(0xFFF0F7F5),

                borderRadius:
                    BorderRadius.circular(16),


                boxShadow: const [

                  BoxShadow(

                    color:
                        Colors.black12,

                    blurRadius: 4,

                    offset:
                        Offset(0,2),

                  ),

                ],

              ),



              child: ListTile(



                contentPadding:
                    const EdgeInsets.symmetric(

                  horizontal: 18,

                  vertical: 8,

                ),



                leading: Container(


                  padding:
                      const EdgeInsets.all(10),


                  decoration:
                      BoxDecoration(

                    color:
                        AppTheme.demoBorder,

                    borderRadius:
                        BorderRadius.circular(12),

                  ),



                  child: const Icon(

                    Icons.business,

                    color:
                        AppTheme.accentDark,

                  ),

                ),




                title: Text(

                  tenant.nombreComercial,

                  style:
                      const TextStyle(

                    fontWeight:
                        FontWeight.bold,

                  ),

                ),




                subtitle: Text(

                  tenant.razonSocial,

                ),




                trailing:
                    const Icon(

                  Icons.arrow_forward_ios,

                  size: 16,

                ),


              ),


            );


          }),


        ],

      ),

    );


  }


}