import 'package:flutter/material.dart';
import '../data/tenant_service.dart';


class TenantFormPage extends StatefulWidget {

  const TenantFormPage({
    super.key,
  });


  @override
  State<TenantFormPage> createState() =>
      _TenantFormPageState();

}



class _TenantFormPageState
    extends State<TenantFormPage> {


  final TenantService _service =
      TenantService();


  final _nombreController =
      TextEditingController();

  final _razonController =
      TextEditingController();

  final _subdomainController =
      TextEditingController();

  final _nitController =
      TextEditingController();

  final _emailController =
      TextEditingController();

  final _telefonoController =
      TextEditingController();



  bool loading = false;



  Future<void> _guardar() async {


    setState(() {
      loading = true;
    });



    try {


      await _service.createTenant({

        "nombre_comercial":
            _nombreController.text,

        "razon_social":
            _razonController.text,

        "subdomain":
            _subdomainController.text,

        "nit":
            _nitController.text,

        "email_contacto":
            _emailController.text,

        "telefono":
            _telefonoController.text,

        "estado": "ACTIVO",

      });



      if(!mounted) return;


      Navigator.pop(
        context,
        true,
      );


    } catch(e){


      ScaffoldMessenger.of(context)
          .showSnackBar(
        SnackBar(
          content: Text(
            e.toString(),
          ),
        ),
      );


    }


    setState(() {
      loading = false;
    });


  }





  @override
  Widget build(BuildContext context) {


    return Scaffold(

      appBar: AppBar(
        title: const Text(
          'Nueva empresa',
        ),
      ),


      body: Padding(

        padding:
            const EdgeInsets.all(20),


        child: ListView(

          children: [


            TextField(
              controller:
                  _nombreController,
              decoration:
                  const InputDecoration(
                    labelText:
                        'Nombre comercial',
                  ),
            ),


            TextField(
              controller:
                  _razonController,
              decoration:
                  const InputDecoration(
                    labelText:
                        'Razón social',
                  ),
            ),


            TextField(
              controller:
                  _subdomainController,
              decoration:
                  const InputDecoration(
                    labelText:
                        'Subdomain',
                  ),
            ),


            TextField(
              controller:
                  _nitController,
              decoration:
                  const InputDecoration(
                    labelText:
                        'NIT',
                  ),
            ),


            TextField(
              controller:
                  _emailController,
              decoration:
                  const InputDecoration(
                    labelText:
                        'Email contacto',
                  ),
            ),


            TextField(
              controller:
                  _telefonoController,
              decoration:
                  const InputDecoration(
                    labelText:
                        'Teléfono',
                  ),
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

              loading

              ? const CircularProgressIndicator()

              :

              const Text(
                'Guardar empresa',
              ),

            ),


          ],

        ),

      ),

    );

  }

}