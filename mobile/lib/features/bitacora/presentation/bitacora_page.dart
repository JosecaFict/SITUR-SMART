import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../data/bitacora_service.dart';
import '../models/bitacora.dart';

import '../../../core/theme/app_theme.dart';



class BitacoraPage extends StatefulWidget {

  const BitacoraPage({
    super.key,
  });


  @override
  State<BitacoraPage> createState() =>
      _BitacoraPageState();

}



class _BitacoraPageState extends State<BitacoraPage> {


  final BitacoraService _service =
      BitacoraService();


  List<Bitacora> _registros = [];


  bool _loading = true;


  String? _error;



  @override
  void initState(){

    super.initState();

    _loadBitacora();

  }





  Future<void> _loadBitacora() async {

    try {

      final data =
          await _service.getBitacora();


      setState((){

        _registros = data;

        _loading = false;

      });


    } catch(e){

      setState((){

        _error = e.toString();

        _loading = false;

      });

    }

  }






  @override
  Widget build(BuildContext context){


    if(_loading){

      return const Center(
        child: CircularProgressIndicator(),
      );

    }



    if(_error != null){

      return Center(
        child: Text(_error!),
      );

    }




    return RefreshIndicator(

      onRefresh: _loadBitacora,


      child: ListView(

        padding:
            const EdgeInsets.all(20),


        children:[



          const Text(

            'Bitácora',

            style: TextStyle(

              fontSize:32,

              fontWeight:
                  FontWeight.bold,

              color:
                  AppTheme.titleColor,

            ),

          ),



          const SizedBox(
            height:6,
          ),




          const Text(

            'Historial de cambios de toda la plataforma. Filtra por empresa para revisar una en particular.',

            style: TextStyle(

              fontSize:16,

              color:
                  AppTheme.textSecondary,

            ),

          ),




          const SizedBox(
            height:22,
          ),




          _filters(),



          const SizedBox(
            height:22,
          ),




          _table(),



        ],

      ),

    );


  }









  Widget _filters(){


    return Container(

      padding:
          const EdgeInsets.all(18),


      decoration:
          BoxDecoration(

        color:
            Colors.white,

        borderRadius:
            BorderRadius.circular(18),


        border:
            Border.all(

              color:
                  AppTheme.demoBorder,

            ),

      ),


      child: Column(

        crossAxisAlignment:
            CrossAxisAlignment.start,


        children:[



          _select(
            'Empresa',
            'Todas las empresas',
          ),



          const SizedBox(
            height:15,
          ),



          _select(
            'Entidad',
            'Todas',
          ),



          const SizedBox(
            height:15,
          ),



          _select(
            'Acción',
            'Todas',
          ),




          const SizedBox(
            height:15,
          ),




          const Text(

            'Usuario',

            style: TextStyle(

              fontWeight:
                  FontWeight.bold,

            ),

          ),




          const SizedBox(
            height:8,
          ),




          TextField(

            decoration:
                InputDecoration(

              hintText:
                  'Nombre o correo',

              prefixIcon:
                  const Icon(
                    Icons.search,
                  ),


              border:
                  OutlineInputBorder(

                borderRadius:
                    BorderRadius.circular(14),

              ),

            ),

          ),





          const SizedBox(
            height:15,
          ),




          Column(

            children:[

              _dateBox(
                'Desde',
              ),


              const SizedBox(
                height:12,
              ),


              _dateBox(
                'Hasta',
              ),


            ],

          ),




          const SizedBox(
            height:18,
          ),





          Wrap(

            spacing:
                12,


            runSpacing:
                12,


            children:[



              ElevatedButton(

                onPressed:(){},


                style:
                    ElevatedButton.styleFrom(

                  backgroundColor:
                      AppTheme.accent,

                  foregroundColor:
                      Colors.white,

                ),


                child:
                    const Text(
                      'Aplicar filtros',
                    ),

              ),




              OutlinedButton(

                onPressed:(){},


                child:
                    const Text(
                      'Limpiar',
                    ),

              ),




              OutlinedButton.icon(

                onPressed:
                    _loadBitacora,


                icon:
                    const Icon(
                      Icons.refresh,
                    ),


                label:
                    const Text(
                      'Actualizar',
                    ),

              ),


            ],


          ),




        ],


      ),


    );


  }









  Widget _select(
    String title,
    String value,
  ){


    return Column(

      crossAxisAlignment:
          CrossAxisAlignment.start,


      children:[



        Text(

          title,

          style:
              const TextStyle(

            fontWeight:
                FontWeight.bold,

          ),

        ),




        const SizedBox(
          height:8,
        ),




        Container(

          height:
              52,


          padding:
              const EdgeInsets.symmetric(
                horizontal:15,
              ),



          decoration:
              BoxDecoration(

            border:
                Border.all(
                  color:
                      Colors.grey.shade300,
                ),


            borderRadius:
                BorderRadius.circular(14),


          ),




          child: Row(

            mainAxisAlignment:
                MainAxisAlignment.spaceBetween,


            children:[


              Text(value),



              const Icon(
                Icons.keyboard_arrow_down,
              ),


            ],


          ),


        ),


      ],


    );


  }









  Widget _dateBox(
    String title,
  ){


    return Column(

      crossAxisAlignment:
          CrossAxisAlignment.start,


      children:[



        Text(

          title,

          style:
              const TextStyle(

            fontWeight:
                FontWeight.bold,

          ),

        ),




        const SizedBox(
          height:8,
        ),




        Container(

          height:
              52,


          padding:
              const EdgeInsets.symmetric(
                horizontal:12,
              ),



          decoration:
              BoxDecoration(

            border:
                Border.all(
                  color:
                      Colors.grey.shade300,
                ),


            borderRadius:
                BorderRadius.circular(14),


          ),




          child: Row(

            mainAxisAlignment:
                MainAxisAlignment.spaceBetween,


            children:[



              const Text(
                'dd/mm/aaaa',
              ),



              const Icon(
                Icons.calendar_month,
              ),


            ],


          ),


        ),


      ],


    );


  }









  Widget _table(){


    return Container(

      decoration:
          BoxDecoration(

        color:
            Colors.white,


        borderRadius:
            BorderRadius.circular(18),



        border:
            Border.all(

              color:
                  AppTheme.demoBorder,

            ),


      ),




      child:
          SingleChildScrollView(

        scrollDirection:
            Axis.horizontal,


        child:
            DataTable(

          columnSpacing:
              35,


          columns:[


            const DataColumn(
              label:
                  Text(
                    'Fecha',
                  ),
            ),



            const DataColumn(
              label:
                  Text(
                    'Usuario',
                  ),
            ),




            const DataColumn(
              label:
                  Text(
                    'Empresa',
                  ),
            ),



          ],





          rows:


              _registros.map(


                (registro)=>


                    DataRow(

                  cells:[



                    DataCell(

                      Text(

                        DateFormat(
                          'dd/MM/yyyy HH:mm',
                        ).format(
                          registro.fecha,
                        ),

                      ),

                    ),






                    DataCell(

                      SizedBox(

                        width:
                            150,


                        child:
                            Column(

                          mainAxisAlignment:
                              MainAxisAlignment.center,


                          crossAxisAlignment:
                              CrossAxisAlignment.start,


                          children:[



                            Text(

                              registro.usuario ??
                                  'Sistema',


                              style:
                                  const TextStyle(

                                fontWeight:
                                    FontWeight.bold,

                              ),

                            ),



                          ],


                        ),


                      ),


                    ),






                    DataCell(

                      Text(

                        registro.entidad,

                      ),

                    ),




                  ],


                ),



              ).toList(),



        ),


      ),


    );


  }



}