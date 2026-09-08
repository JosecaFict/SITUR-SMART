import 'package:flutter/material.dart';

import '../../data/user_service.dart';
import '../../models/user.dart';
import '../user_form_page.dart';

import '../../../../core/theme/app_theme.dart';


/// Pantalla de administración de usuarios.
///
/// Permite listar, crear, editar y eliminar usuarios.
class UsersPage extends StatefulWidget {

  const UsersPage({
    super.key,
  });


  @override
  State<UsersPage> createState() =>
      _UsersPageState();

}


/// Controla la carga y acciones sobre usuarios.
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



  /// Obtiene usuarios desde el backend.
  Future<void> _loadUsers() async {

    try {

      final users =
          await _userService.getUsers();


      setState(() {

        _users = users;

        _loading = false;

      });


    } catch (e) {

      setState(() {

        _error = e.toString();

        _loading = false;

      });

    }

  }



  /// Abre formulario para crear un usuario.
  Future<void> _createUser() async {

    final result =
        await Navigator.push(

      context,

      MaterialPageRoute(

        builder: (_) =>
            const UserFormPage(),

      ),

    );


    if (result == true) {

      _loadUsers();

    }

  }



  /// Abre formulario para editar un usuario.
  Future<void> _editUser(
    UserModel user,
  ) async {

    final result =
        await Navigator.push(

      context,

      MaterialPageRoute(

        builder: (_) =>
            UserFormPage(
              user: user,
            ),

      ),

    );


    if (result == true) {

      _loadUsers();

    }

  }



  /// Elimina un usuario después de confirmación.
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

            onPressed: () =>
                Navigator.pop(
                  context,
                  false,
                ),

            child:
                const Text(
                  'Cancelar',
                ),

          ),

          TextButton(

            onPressed: () =>
                Navigator.pop(
                  context,
                  true,
                ),

            child:
                const Text(
                  'Eliminar',
                ),

          ),

        ],

      ),

    );


    if (confirm == true) {

      await _userService.deleteUser(
        user.id,
      );

      _loadUsers();

    }

  }



  @override
  Widget build(BuildContext context) {

    return Scaffold(

      floatingActionButton:
          FloatingActionButton.extended(

        backgroundColor:
            AppTheme.accent,

        onPressed:
            _createUser,

        icon:
            const Icon(
              Icons.person_add,
            ),

        label:
            const Text(
              'Nuevo usuario',
            ),

      ),


      body:
          _buildBody(),

    );

  }



  /// Construye la lista visual de usuarios.
  Widget _buildBody() {

    if (_loading) {

      return const Center(
        child:
            CircularProgressIndicator(),
      );

    }


    if (_error != null) {

      return Center(
        child:
            Text(
              _error!,
            ),
      );

    }


    return RefreshIndicator(

      onRefresh:
          _loadUsers,

      child:
          ListView(

        padding:
            const EdgeInsets.all(20),

        children: [

          const Text(

            'Usuarios',

            style:
                TextStyle(

              fontSize:
                  28,

              fontWeight:
                  FontWeight.bold,

              color:
                  AppTheme.titleColor,

            ),

          ),


          const SizedBox(
            height: 8,
          ),


          const Text(

            'Gestiona usuarios y permisos del sistema',

            style:
                TextStyle(

              color:
                  AppTheme.textSecondary,

            ),

          ),


          const SizedBox(
            height: 20,
          ),


          ..._users.map(

            (user) =>
                _UserCard(

              user:
                  user,

              onEdit:
                  () => _editUser(
                    user,
                  ),

              onDelete:
                  () => _deleteUser(
                    user,
                  ),

            ),

          ),

        ],

      ),

    );

  }

}


/// Tarjeta visual de un usuario.
class _UserCard extends StatelessWidget {

  final UserModel user;

  final VoidCallback onEdit;

  final VoidCallback onDelete;


  const _UserCard({

    required this.user,

    required this.onEdit,

    required this.onDelete,

  });



  @override
  Widget build(BuildContext context) {

    return Container(

      margin:
          const EdgeInsets.only(
            bottom: 14,
          ),

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


      child:
          Row(

        children: [

          CircleAvatar(

            backgroundColor:
                AppTheme.accent,

            child:
                Text(

              user.nombres.isNotEmpty
                  ? user.nombres[0]
                  : 'U',

              style:
                  const TextStyle(

                color:
                    Colors.white,

                fontWeight:
                    FontWeight.bold,

              ),

            ),

          ),


          const SizedBox(
            width: 14,
          ),


          Expanded(

            child:
                Column(

              crossAxisAlignment:
                  CrossAxisAlignment.start,


              children: [

                Text(

                  '${user.nombres} ${user.apellidos}',

                  style:
                      const TextStyle(

                    fontWeight:
                        FontWeight.bold,

                    fontSize:
                        16,

                  ),

                ),


                Text(
                  user.email,
                ),


                Text(
                  user.estado,
                  style:
                      const TextStyle(
                        color:
                            AppTheme.accentDark,
                        fontWeight:
                            FontWeight.bold,
                      ),
                ),

              ],

            ),

          ),


          IconButton(

            onPressed:
                onEdit,

            icon:
                const Icon(
                  Icons.edit,
                ),

          ),


          IconButton(

            onPressed:
                onDelete,

            icon:
                const Icon(
                  Icons.delete_outline,
                ),

          ),

        ],

      ),

    );

  }

}
