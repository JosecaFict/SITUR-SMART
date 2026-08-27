import 'package:flutter/material.dart';

import '../../../shared/widgets/situr_app_bar.dart';


class RolesPage extends StatelessWidget {

  const RolesPage({
    super.key,
  });


  @override
  Widget build(BuildContext context) {

    final roles = [

      'SUPER_ADMIN',
      'TENANT_ADMIN',
      'TENANT_OPERADOR',
      'TENANT_VENTAS',
      'TENANT_CAJA',
      'TENANT_RECEPCION',
      'TENANT_LIMPIEZA',

    ];


    return ListView.builder(

      padding: const EdgeInsets.all(20),

      itemCount: roles.length,


      itemBuilder: (context, index){


        return Card(

          margin: const EdgeInsets.only(
            bottom: 12,
          ),


          child: ListTile(

            leading: const Icon(
              Icons.security,
            ),


            title: Text(
              roles[index],
              style: const TextStyle(
                fontWeight: FontWeight.bold,
              ),
            ),


            subtitle: const Text(
              'Rol registrado en SITUR-SMART',
            ),

          ),

        );


      },


    );

  }

}