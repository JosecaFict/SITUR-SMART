import 'package:flutter/material.dart';
import 'package:intl/intl.dart';


class BitacoraPage extends StatelessWidget {

  const BitacoraPage({
    super.key,
  });



  String _fechaActual() {

    final now = DateTime.now();

    return DateFormat('dd/MM/yyyy').format(now);

  }



  String _horaActual() {

    final now = DateTime.now();

    return DateFormat('HH:mm:ss').format(now);

  }




  @override
  Widget build(BuildContext context) {


    final fecha = _fechaActual();

    final hora = _horaActual();



    return ListView(

      padding: const EdgeInsets.all(20),


      children: [



        _buildItem(

          icon: Icons.login,

          titulo: 'Inicio de sesión',

          descripcion:
              'Usuario ingresó al sistema',

          fecha: fecha,

          hora: hora,

        ),




        _buildItem(

          icon: Icons.person_add,

          titulo: 'Usuario creado',

          descripcion:
              'Registro de usuario en plataforma',

          fecha: fecha,

          hora: hora,

        ),




        _buildItem(

          icon: Icons.business,

          titulo: 'Empresa registrada',

          descripcion:
              'Nuevo tenant agregado',

          fecha: fecha,

          hora: hora,

        ),



      ],


    );


  }







  Widget _buildItem({

    required IconData icon,

    required String titulo,

    required String descripcion,

    required String fecha,

    required String hora,

  }) {


    return Card(

      margin:

          const EdgeInsets.only(

        bottom: 14,

      ),



      child: Padding(

        padding:

            const EdgeInsets.all(16),



        child: Column(

          crossAxisAlignment:
              CrossAxisAlignment.start,



          children: [



            Row(

              children: [



                Icon(

                  icon,

                ),



                const SizedBox(
                  width: 12,
                ),



                Text(

                  titulo,

                  style:
                      const TextStyle(

                    fontSize: 16,

                    fontWeight:
                        FontWeight.bold,

                  ),

                ),


              ],

            ),




            const SizedBox(
              height: 10,
            ),




            Text(
              descripcion,
            ),



            const SizedBox(
              height: 12,
            ),




            Row(

              children: [


                const Icon(

                  Icons.calendar_today,

                  size: 16,

                ),



                const SizedBox(
                  width: 6,
                ),



                Text(
                  fecha,
                ),



                const SizedBox(
                  width: 20,
                ),



                const Icon(

                  Icons.access_time,

                  size: 16,

                ),



                const SizedBox(
                  width: 6,
                ),



                Text(
                  hora,
                ),


              ],

            ),



          ],


        ),

      ),

    );


  }



}