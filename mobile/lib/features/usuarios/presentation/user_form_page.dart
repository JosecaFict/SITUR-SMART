import 'package:flutter/material.dart';

import '../data/user_service.dart';
import '../data/role_service.dart';

import '../../tenants/data/tenant_service.dart';

import '../models/role.dart';
import '../models/user.dart';

import '../../tenants/models/tenant.dart';



class UserFormPage extends StatefulWidget {


  final UserModel? user;


  const UserFormPage({

    super.key,

    this.user,

  });



  @override
  State<UserFormPage> createState() =>
      _UserFormPageState();


}






class _UserFormPageState extends State<UserFormPage> {



  final UserService _userService =
      UserService();


  final RoleService _roleService =
      RoleService();


  final TenantService _tenantService =
      TenantService();




  final _formKey =
      GlobalKey<FormState>();




  final TextEditingController _emailController =
      TextEditingController();


  final TextEditingController _nombresController =
      TextEditingController();


  final TextEditingController _apellidosController =
      TextEditingController();


  final TextEditingController _telefonoController =
      TextEditingController();





  List<RoleModel> _roles = [];

  List<Tenant> _tenants = [];



  int? _selectedRole;

  int? _selectedTenant;



  bool _loading = false;

  bool _loadingData = true;



  String _estado = 'ACTIVO';








  bool get _isEditing =>
      widget.user != null;









  @override
  void initState() {


    super.initState();


    if(_isEditing){


      _emailController.text =
          widget.user!.email;


      _nombresController.text =
          widget.user!.nombres;


      _apellidosController.text =
          widget.user!.apellidos;


      _telefonoController.text =
          widget.user!.telefono ?? '';


      _estado =
          widget.user!.estado;


    }



    _loadData();


  }









  Future<void> _loadData() async {


    try {


      final tenants =
          await _tenantService.getTenants();

      final initialTenant = tenants.isNotEmpty ? tenants.first.id : null;
      final roles = await _roleService.getRoles(tenantId: initialTenant);



      setState(() {


        _roles = roles;

        _tenants = tenants;

        _selectedTenant = initialTenant;

        _loadingData = false;



      });



    } catch(e){


      setState(() {

        _loadingData = false;

      });


    }



  }









  Future<void> _saveUser() async {



    if(!_formKey.currentState!.validate()){

      return;

    }






    setState(() {


      _loading = true;


    });





    try {


      if(_isEditing){



        await _userService.updateUser(

          widget.user!.id,

          email:
              _emailController.text.trim(),

          nombres:
              _nombresController.text.trim(),

          apellidos:
              _apellidosController.text.trim(),

          telefono:
              _telefonoController.text.trim(),

          estado:
              _estado,

        );



      }else{



        if(_selectedRole == null ||
           _selectedTenant == null){


          throw Exception(
            'Seleccione empresa y rol',
          );


        }




        await _userService.createUser(


          email:
              _emailController.text,


          nombres:
              _nombresController.text,


          apellidos:
              _apellidosController.text,


          telefono:
              _telefonoController.text.isEmpty

              ? null

              : _telefonoController.text,


          estado:
              _estado,


          roleCode:
              _roles.firstWhere((role) => role.id == _selectedRole).codigo,


          tenantId:
              _selectedTenant!,


        );

      }






      if(mounted){


        Navigator.pop(

          context,

          true,

        );


      }





    }catch(e){



      ScaffoldMessenger.of(context)
          .showSnackBar(

        SnackBar(

          content:
              Text(
                e.toString(),
              ),

        ),

      );



    }finally{


      setState(() {


        _loading = false;


      });



    }


  }









  @override
  Widget build(BuildContext context) {


    return Scaffold(


      appBar: AppBar(

        title:
            Text(

              _isEditing

              ? 'Editar usuario'

              : 'Crear usuario',

            ),

      ),





      body:

      _loadingData


      ?


      const Center(

        child:
            CircularProgressIndicator(),

      )



      :


      Padding(

        padding:
            const EdgeInsets.all(20),


        child:

        Form(

          key:
              _formKey,


          child:

          ListView(

            children: [



              TextFormField(

                controller:
                    _emailController,


                decoration:
                    const InputDecoration(

                  labelText:
                      'Email',

                ),

              ),





              TextFormField(

                controller:
                    _nombresController,


                decoration:
                    const InputDecoration(

                  labelText:
                      'Nombres',

                ),

              ),





              TextFormField(

                controller:
                    _apellidosController,


                decoration:
                    const InputDecoration(

                  labelText:
                      'Apellidos',

                ),

              ),





              TextFormField(

                controller:
                    _telefonoController,


                decoration:
                    const InputDecoration(

                  labelText:
                      'Teléfono',

                ),

              ),





              DropdownButtonFormField<String>(


                value:
                    _estado,


                decoration:
                    const InputDecoration(

                  labelText:
                      'Estado',

                ),



                items: const [


                  DropdownMenuItem(

                    value:
                        'ACTIVO',

                    child:
                        Text('ACTIVO'),

                  ),


                  DropdownMenuItem(

                    value:
                        'INACTIVO',

                    child:
                        Text('INACTIVO'),

                  ),


                ],



                onChanged:(value){


                  setState((){

                    _estado=value!;


                  });


                },


              ),





              if(!_isEditing)...[



                DropdownButtonFormField<int>(


                  value:
                      _selectedTenant,


                  decoration:
                      const InputDecoration(

                    labelText:
                        'Empresa',

                  ),


                  items:

                  _tenants.map((tenant){


                    return DropdownMenuItem(

                      value:
                          tenant.id,


                      child:
                          Text(
                            tenant.nombreComercial,
                          ),


                    );


                  }).toList(),



                  onChanged:(value) async {
                    if (value == null) return;
                    setState(() {
                      _selectedTenant = value;
                      _selectedRole = null;
                    });
                    final roles = await _roleService.getRoles(tenantId: value);
                    if (mounted) setState(() => _roles = roles);
                  },



                ),






                DropdownButtonFormField<int>(


                  value:
                      _selectedRole,


                  decoration:
                      const InputDecoration(

                    labelText:
                        'Rol',

                  ),


                  items:
                  _roles.map((role){

                    return DropdownMenuItem(

                      value:
                          role.id,


                      child:
                          Text(
                            role.nombre,
                          ),


                    );


                  }).toList(),



                  onChanged:(value){


                    setState((){


                      _selectedRole=value;


                    });


                  },


                ),



              ],





              const SizedBox(

                height:30,

              ),





              ElevatedButton(


                onPressed:

                    _loading

                    ? null

                    : _saveUser,



                child:

                    _loading

                    ?

                    const CircularProgressIndicator()

                    :

                    Text(

                      _isEditing

                      ? 'Guardar cambios'

                      : 'Crear usuario',

                    ),



              ),



            ],

          ),


        ),


      ),



    );


  }


}
