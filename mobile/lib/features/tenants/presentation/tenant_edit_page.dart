import 'package:flutter/material.dart';

import '../data/tenant_service.dart';
import '../models/tenant.dart';


class TenantEditPage extends StatefulWidget {

  final Tenant tenant;


  const TenantEditPage({
    super.key,
    required this.tenant,
  });



  @override
  State<TenantEditPage> createState() =>
      _TenantEditPageState();

}



class _TenantEditPageState
    extends State<TenantEditPage> {


  final TenantService _service =
      TenantService();



  late TextEditingController nombre;
  late TextEditingController razon;
  late TextEditingController subdomain;
  late TextEditingController nit;
  late TextEditingController email;
  late TextEditingController telefono;



  bool loading = false;



  @override
  void initState() {

    super.initState();


    nombre = TextEditingController(
      text: widget.tenant.nombreComercial,
    );


    razon = TextEditingController(
      text: widget.tenant.razonSocial,
    );


    subdomain = TextEditingController(
      text: widget.tenant.subdomain,
    );


    nit = TextEditingController(
      text: widget.tenant.nit,
    );


    email = TextEditingController(
      text: widget.tenant.emailContacto,
    );


    telefono = TextEditingController(
      text: widget.tenant.telefono,
    );


  }







  Future<void> _guardar() async {


    setState(() {
      loading = true;
    });



    await _service.updateTenant(

      widget.tenant.id,

      {

        "nombre_comercial": nombre.text,

        "razon_social": razon.text,

        "subdomain": subdomain.text,

        "nit": nit.text,

        "email_contacto": email.text,

        "telefono": telefono.text,

        "estado": "ACTIVO",

      },

    );



    if(!mounted) return;


    Navigator.pop(
      context,
      true,
    );


  }







  Widget campo(
    String titulo,
    TextEditingController controller,
  ){

    return TextField(

      controller: controller,

      decoration: InputDecoration(
        labelText: titulo,
      ),

    );

  }





  @override
  Widget build(BuildContext context) {


    return Scaffold(

      appBar: AppBar(
        title: const Text(
          'Editar empresa',
        ),
      ),


      body: Padding(

        padding:
            const EdgeInsets.all(20),


        child: ListView(

          children: [


            campo(
              'Nombre comercial',
              nombre,
            ),


            campo(
              'Razón social',
              razon,
            ),


            campo(
              'Subdomain',
              subdomain,
            ),


            campo(
              'NIT',
              nit,
            ),


            campo(
              'Email',
              email,
            ),


            campo(
              'Teléfono',
              telefono,
            ),


            const SizedBox(
              height: 30,
            ),


            ElevatedButton(

              onPressed:
                  loading
                  ? null
                  : _guardar,


              child:
                  const Text(
                    'Guardar cambios',
                  ),

            )

          ],

        ),

      ),

    );

  }

}