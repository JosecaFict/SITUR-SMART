import 'package:flutter/material.dart';

import '../../data/user_service.dart';
import '../../models/user.dart';
import '../user_form_page.dart';



class UsersPage extends StatefulWidget {


  const UsersPage({
    super.key,
  });



  @override
  State<UsersPage> createState() =>
      _UsersPageState();


}






class _UsersPageState extends State<UsersPage> {



  final UserService _userService =
      UserService();




  List<UserModel> _users = [];

  bool _loading = true;

  String? _error;







  @override
  void initState() {

    super.initState();

    _loadUsers();

  }







  Future<void> _loadUsers() async {


    try {


      final users =
          await _userService.getUsers();



      setState(() {


        _users = users;

        _loading = false;


      });



    } catch(e) {


      setState(() {


        _error = e.toString();

        _loading = false;


      });


    }


  }









  Future<void> _openCreateUser() async {


    final created =
        await Navigator.push(


      context,


      MaterialPageRoute(


        builder: (_) =>
            const UserFormPage(),


      ),


    );



    if(created == true){


      setState(() {

        _loading = true;

      });


      _loadUsers();


    }


  }









  Future<void> _editUser(
    UserModel user,
  ) async {



    final updated =
        await Navigator.push(


      context,


      MaterialPageRoute(


        builder: (_) =>
            UserFormPage(
              user: user,
            ),


      ),


    );



    if(updated == true){


      setState(() {

        _loading = true;

      });


      _loadUsers();


    }



  }









  Future<void> _deleteUser(
    UserModel user,
  ) async {



    final confirm =
        await showDialog<bool>(


      context: context,


      builder: (_) => AlertDialog(


        title:
            const Text(
              'Eliminar usuario',
            ),



        content:
            Text(

              '¿Eliminar ${user.email}?',

            ),



        actions: [



          TextButton(


            onPressed: (){


              Navigator.pop(
                context,
                false,
              );


            },


            child:
                const Text(
                  'Cancelar',
                ),


          ),





          TextButton(


            onPressed: (){


              Navigator.pop(
                context,
                true,
              );


            },


            child:
                const Text(
                  'Eliminar',
                ),


          ),



        ],


      ),


    );





    if(confirm != true){

      return;

    }






    try {



      await _userService.deleteUser(
        user.id,
      );



      _loadUsers();




    } catch(e){



      ScaffoldMessenger.of(context)
          .showSnackBar(


        SnackBar(

          content:
              Text(
                e.toString(),
              ),

        ),


      );



    }



  }









  @override
  Widget build(BuildContext context) {


    return Scaffold(


      appBar: AppBar(


        title:
            const Text(
              'Usuarios',
            ),




        actions: [



          IconButton(


            onPressed:
                _openCreateUser,


            icon:
                const Icon(
                  Icons.person_add,
                ),



          ),



        ],



      ),




      body:
          _buildBody(),



    );


  }









  Widget _buildBody(){



    if(_loading){


      return const Center(

        child:
            CircularProgressIndicator(),

      );


    }







    if(_error != null){


      return Center(

        child:
            Text(
              _error!,
            ),

      );


    }









    return ListView.builder(



      padding:
          const EdgeInsets.all(20),




      itemCount:
          _users.length,





      itemBuilder:
          (context,index){



        final user =
            _users[index];







        return Card(



          margin:
              const EdgeInsets.only(
                bottom: 12,
              ),






          child: ListTile(




            leading:
                const CircleAvatar(


              child:
                  Icon(
                    Icons.person,
                  ),


            ),








            title:
                Text(

                  '${user.nombres} ${user.apellidos}',

                ),









            subtitle:
                Column(


                  crossAxisAlignment:
                      CrossAxisAlignment.start,


                  children: [


                    Text(
                      user.email,
                    ),


                    Text(
                      user.estado,
                    ),



                  ],


                ),







            trailing:
                Row(


                  mainAxisSize:
                      MainAxisSize.min,



                  children: [



                    IconButton(


                      icon:
                          const Icon(
                            Icons.edit,
                          ),



                      onPressed: (){


                        _editUser(
                          user,
                        );


                      },


                    ),





                    IconButton(


                      icon:
                          const Icon(
                            Icons.delete,
                          ),




                      onPressed: (){


                        _deleteUser(
                          user,
                        );


                      },


                    ),



                  ],


                ),





          ),



        );



      },



    );



  }





}