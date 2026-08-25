import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/storage/token_storage.dart';

import '../../../../core/theme/app_theme.dart';
import '../../data/auth_service.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _formKey = GlobalKey<FormState>();

  final _emailController =
      TextEditingController(text: 'admin@situr-smart.com');

  final _passwordController = TextEditingController();

  final AuthService _authService = AuthService();

  bool _obscurePassword = true;
  bool _rememberMe = false;
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

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


await TokenStorage().saveTokens(
  access: response['access'],
  refresh: response['refresh'],
);


if (!mounted) return;

debugPrint(response.toString());

context.go('/home');

    } catch (e) {
      if (!mounted) return;

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
    final media = MediaQuery.of(context);
    final isWide = media.size.width >= 900;

    return Scaffold(
      resizeToAvoidBottomInset: true,
      body: SafeArea(
        child: Row(
          children: [
            if (isWide) const Expanded(
              flex: 11,
              child: _BrandPanel(),
            ),

            Expanded(
              flex: 9,
              child: Align(
                alignment: Alignment.topCenter,
                child: SingleChildScrollView(
                  padding: EdgeInsets.fromLTRB(
                    24,
                    isWide ? 40 : 22,
                    24,
                    24 + media.viewInsets.bottom,
                  ),

                  child: ConstrainedBox(
                    constraints: const BoxConstraints(
                      maxWidth: 430,
                    ),

                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [

                        if (!isWide)
                          const _MobileLogo(),

                        if (!isWide)
                          const SizedBox(height: 24),

                        Text(
                          'Bienvenido de vuelta',
                          style: theme.textTheme.headlineMedium?.copyWith(
                            fontSize: 38,
                          ),
                        ),

                        const SizedBox(height: 8),

                        Text(
                          'Ingresa tus credenciales para continuar',
                          style: theme.textTheme.bodyLarge?.copyWith(
                            color: AppTheme.textSecondary,
                          ),
                        ),

                        const SizedBox(height: 20),

                        const _DemoHint(),

                        const SizedBox(height: 16),

                        if (_errorMessage != null)
                          _ErrorMessage(
                            message: _errorMessage!,
                          ),

                        Form(
                          key: _formKey,

                          child: Column(
                            crossAxisAlignment:
                                CrossAxisAlignment.start,

                            children: [

                              const _FieldLabel(
                                'Correo electrónico',
                              ),

                              const SizedBox(height: 8),

                              TextFormField(
                                controller: _emailController,
                                keyboardType:
                                    TextInputType.emailAddress,

                                textInputAction:
                                    TextInputAction.next,

                                decoration:
                                    const InputDecoration(
                                  hintText:
                                      'admin@situr-smart.com',
                                  suffixIcon:
                                      Icon(Icons.mail_outline),
                                ),

                                validator: (value) {

                                  if (value == null ||
                                      value.trim().isEmpty) {
                                    return 'El correo es obligatorio.';
                                  }

                                  if (!RegExp(
                                    r'^[^@\s]+@[^@\s]+\.[^@\s]+$',
                                  ).hasMatch(value.trim())) {
                                    return 'Ingresa un correo electrónico válido.';
                                  }

                                  return null;
                                },

                                enabled: !_isLoading,
                              ),

                              const SizedBox(height: 16),

                              const _FieldLabel(
                                'Contraseña',
                              ),

                              const SizedBox(height: 8),

                              TextFormField(
                                controller:
                                    _passwordController,

                                obscureText:
                                    _obscurePassword,

                                textInputAction:
                                    TextInputAction.done,

                                onFieldSubmitted: (_) {
                                  if (!_isLoading) {
                                    _submit();
                                  }
                                },

                                decoration:
                                    InputDecoration(
                                  hintText: '••••••••',

                                  suffixIcon:
                                      IconButton(
                                    onPressed:
                                        _isLoading
                                            ? null
                                            : () {
                                                setState(() {
                                                  _obscurePassword =
                                                      !_obscurePassword;
                                                });
                                              },

                                    icon: Icon(
                                      _obscurePassword
                                          ? Icons
                                              .visibility_outlined
                                          : Icons
                                              .visibility_off_outlined,
                                    ),
                                  ),
                                ),

                                validator: (value) =>
                                    value == null ||
                                            value.isEmpty
                                        ? 'La contraseña es obligatoria.'
                                        : null,

                                enabled: !_isLoading,
                              ),                              const SizedBox(height: 18),

                              Row(
                                children: [
                                  Checkbox(
                                    value: _rememberMe,
                                    onChanged: _isLoading
                                        ? null
                                        : (value) {
                                            setState(() {
                                              _rememberMe =
                                                  value ?? false;
                                            });
                                          },
                                  ),

                                  const Text(
                                    'Recordarme',
                                  ),

                                  const Spacer(),

                                  TextButton(
                                    onPressed: _isLoading
                                        ? null
                                        : () {
                                            context.push(
                                              '/recuperar-contrasena',
                                            );
                                          },

                                    child: const Text(
                                      '¿Olvidaste tu contraseña?',
                                    ),
                                  ),
                                ],
                              ),

                              const SizedBox(height: 18),

                              SizedBox(
                                width: double.infinity,
                                height: 52,

                                child: ElevatedButton(
                                  onPressed:
                                      _isLoading
                                          ? null
                                          : _submit,

                                  child: _isLoading
                                      ? const SizedBox(
                                          width: 22,
                                          height: 22,
                                          child:
                                              CircularProgressIndicator(
                                            strokeWidth: 2,
                                          ),
                                        )
                                      : const Text(
                                          'Iniciar sesión',
                                        ),
                                ),
                              ),

                              const SizedBox(height: 18),

                              Center(
                                child: TextButton(
                                  onPressed: _isLoading
                                      ? null
                                      : () {
                                          context.push(
                                            '/registrar-usuario',
                                          );
                                        },

                                  child: const Text(
                                    '¿No tienes cuenta? Regístrate',
                                  ),
                                ),
                              ),

                              const SizedBox(height: 20),

                              const Divider(),

                              const SizedBox(height: 12),

                              Center(
                                child: Text(
                                  'SITUR-SMART © 2026',
                                  style: theme.textTheme.bodySmall
                                      ?.copyWith(
                                    color:
                                        AppTheme.textSecondary,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}


class _FieldLabel extends StatelessWidget {
  final String text;

  const _FieldLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: Theme.of(context)
          .textTheme
          .labelLarge,
    );
  }
}


class _ErrorMessage extends StatelessWidget {
  final String message;

  const _ErrorMessage({
    required this.message,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,

      margin: const EdgeInsets.only(
        bottom: 16,
      ),

      padding: const EdgeInsets.all(12),

      decoration: BoxDecoration(
        color: Colors.red.withValues(
          alpha: 0.08,
        ),

        borderRadius:
            BorderRadius.circular(12),

        border: Border.all(
          color: Colors.red.withValues(
            alpha: 0.3,
          ),
        ),
      ),

      child: Text(
        message,
        style: const TextStyle(
          color: Colors.red,
        ),
      ),
    );
  }
}


class _MobileLogo extends StatelessWidget {
  const _MobileLogo();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 46,
          height: 46,

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
            fontSize: 20,
            fontWeight: FontWeight.bold,
          ),
        ),
      ],
    );
  }
}


class _BrandPanel extends StatelessWidget {
  const _BrandPanel();

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppTheme.accent,

      padding: const EdgeInsets.all(48),

      child: Column(
        mainAxisAlignment:
            MainAxisAlignment.center,

        crossAxisAlignment:
            CrossAxisAlignment.start,

        children: [

          const Icon(
            Icons.travel_explore,
            size: 80,
            color: Colors.white,
          ),

          const SizedBox(height: 24),

          const Text(
            'SITUR-SMART',
            style: TextStyle(
              color: Colors.white,
              fontSize: 42,
              fontWeight: FontWeight.bold,
            ),
          ),

          const SizedBox(height: 12),

          const Text(
            'Plataforma turística inteligente '
            'para empresas y usuarios.',
            style: TextStyle(
              color: Colors.white70,
              fontSize: 18,
            ),
          ),
        ],
      ),
    );
  }
}


class _DemoHint extends StatelessWidget {
  const _DemoHint();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),

      decoration: BoxDecoration(
        color: AppTheme.accent.withValues(
  alpha: 0.08,
),

        borderRadius:
            BorderRadius.circular(12),
      ),

      child: const Text(
        'Usuario prueba: admin@situr-smart.com',
      ),
    );
  }
}