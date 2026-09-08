// Archivo actualizado:
// - Eliminado usuario demo.
// - Eliminados datos de prueba.
// - Login guarda usuario autenticado.
// - Comentarios únicamente por clase y función.

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/storage/token_storage.dart';
import '../../../../core/theme/app_theme.dart';
import '../../data/auth_service.dart';


/// Pantalla de autenticación de usuarios.
class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}


/// Controla el formulario, validaciones y proceso de login.
class _LoginPageState extends State<LoginPage> {

  final _formKey = GlobalKey<FormState>();

  final _emailController = TextEditingController();

  final _passwordController = TextEditingController();

  final AuthService _authService = AuthService();

  bool _obscurePassword = true;

  bool _isLoading = false;

  bool _rememberMe = false;

  String? _errorMessage;


  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }


  /// Realiza autenticación y guarda la sesión del usuario.
  Future<void> _submit() async {

    FocusScope.of(context).unfocus();

    if (!(_formKey.currentState?.validate() ?? false)) {
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {

      final response = await _authService.login(
        email: _emailController.text.trim(),
        password: _passwordController.text,
      );


      final storage = TokenStorage();


      await storage.saveTokens(
        access: response['access'],
        refresh: response['refresh'],
      );


      await storage.saveUser(
        response['user'],
      );


      if (!mounted) {
        return;
      }


      context.go('/dashboard');


    } catch (e) {

      if (!mounted) {
        return;
      }

      setState(() {
        _errorMessage = e.toString();
      });


    } finally {

      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }

    }
  }


  @override
  Widget build(BuildContext context) {

    final theme = Theme.of(context);

    return Scaffold(

      backgroundColor: Colors.white,

      body: SafeArea(

        child: Center(

          child: SingleChildScrollView(

            padding: const EdgeInsets.all(28),

            child: Form(

              key: _formKey,

              child: Column(

                crossAxisAlignment:
                    CrossAxisAlignment.start,

                children: [

                  const _MobileLogo(),

                  const SizedBox(height: 40),


                  Text(
                    'Bienvenido de vuelta',
                    style: theme.textTheme.headlineMedium,
                  ),


                  const SizedBox(height: 10),


                  Text(
                    'Ingresa tus credenciales para continuar',
                    style: theme.textTheme.bodyLarge?.copyWith(
                      color: AppTheme.textSecondary,
                    ),
                  ),


                  const SizedBox(height: 30),


                  if (_errorMessage != null)
                    _ErrorMessage(
                      message: _errorMessage!,
                    ),


                  TextFormField(

                    controller: _emailController,

                    decoration:
                        const InputDecoration(
                      labelText: 'Correo electrónico',
                      prefixIcon:
                          Icon(Icons.email_outlined),
                    ),

                    validator: (value) {
                      if (value == null ||
                          value.trim().isEmpty) {
                        return 'El correo es obligatorio.';
                      }

                      return null;
                    },
                  ),


                  const SizedBox(height: 20),


                  TextFormField(

                    controller: _passwordController,

                    obscureText: _obscurePassword,

                    decoration: InputDecoration(

                      labelText: 'Contraseña',

                      prefixIcon:
                          const Icon(Icons.lock_outline),

                      suffixIcon:
                          IconButton(

                        icon: Icon(
                          _obscurePassword
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined,
                        ),

                        onPressed: () {
                          setState(() {
                            _obscurePassword =
                                !_obscurePassword;
                          });
                        },

                      ),
                    ),

                    validator: (value) {

                      if (value == null ||
                          value.isEmpty) {

                        return 'La contraseña es obligatoria.';
                      }

                      return null;
                    },
                  ),


                  const SizedBox(height: 15),


                  Row(

                    children: [

                      Checkbox(
                        value: _rememberMe,

                        onChanged: (value) {

                          setState(() {
                            _rememberMe = value ?? false;
                          });

                        },
                      ),

                      const Text(
                        'Recordarme',
                      ),
                    ],
                  ),


                  const SizedBox(height: 20),


                  SizedBox(

                    width: double.infinity,

                    height: 52,

                    child: ElevatedButton(

                      onPressed:
                          _isLoading
                              ? null
                              : _submit,

                      child:
                          _isLoading
                              ? const CircularProgressIndicator()
                              : const Text(
                                  'Iniciar sesión',
                                ),
                    ),
                  ),

                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}


/// Muestra el logo principal del sistema.
class _MobileLogo extends StatelessWidget {

  const _MobileLogo();


  @override
  Widget build(BuildContext context) {

    return Row(

      children: [

        Container(

          width: 50,

          height: 50,

          decoration: BoxDecoration(

            color: AppTheme.accent,

            borderRadius:
                BorderRadius.circular(14),

          ),

          child: const Icon(
            Icons.travel_explore,
            color: Colors.white,
          ),
        ),


        const SizedBox(width: 12),


        const Text(
          'SITUR-SMART',
          style: TextStyle(
            fontSize: 22,
            fontWeight: FontWeight.bold,
          ),
        ),

      ],
    );
  }
}


/// Muestra errores del proceso de autenticación.
class _ErrorMessage extends StatelessWidget {

  final String message;


  const _ErrorMessage({
    required this.message,
  });


  @override
  Widget build(BuildContext context) {

    return Padding(

      padding:
          const EdgeInsets.only(
            bottom: 16,
          ),

      child: Text(

        message,

        style:
            const TextStyle(
              color: Colors.red,
            ),
      ),
    );
  }
}
