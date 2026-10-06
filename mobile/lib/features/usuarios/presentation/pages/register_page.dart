import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../data/auth_service.dart';

class RegisterPage extends StatefulWidget {
  const RegisterPage({super.key});

  @override
  State<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends State<RegisterPage> {
  final _formKey = GlobalKey<FormState>();
  final _nombresController = TextEditingController();
  final _apellidosController = TextEditingController();
  final _telefonoController = TextEditingController();
  final _emailController = TextEditingController();
  final AuthService _authService = AuthService();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();

  bool _obscurePassword = true;
  bool _obscureConfirmPassword = true;
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void dispose() {
    _nombresController.dispose();
    _apellidosController.dispose();
    _telefonoController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
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
      final response = await _authService.register(
        nombres: _nombresController.text.trim(),
        apellidos: _apellidosController.text.trim(),
        email: _emailController.text.trim().toLowerCase(),
        password: _passwordController.text,
        telefono: _telefonoController.text.trim(),
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Cuenta creada. ¡Bienvenido a SITUR-SMART!')),
      );
      // El backend devuelve la sesión iniciada: no hace falta volver al login.
      context.go(AuthService.homeRouteFor(response['user'] as Map<String, dynamic>?));
    } catch (e) {
      if (!mounted) return;
      setState(() => _errorMessage = e.toString());
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Widget _label(String text) => Text(
        text,
        style: const TextStyle(
          fontSize: 15,
          color: AppTheme.labelColor,
          fontWeight: FontWeight.w600,
        ),
      );

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final media = MediaQuery.of(context);
    final isWide = media.size.width >= 900;

    return Scaffold(
      resizeToAvoidBottomInset: true,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            return Row(
              children: [
                if (isWide)
                  Expanded(
                    flex: 11,
                    child: Container(
                      padding: const EdgeInsets.fromLTRB(28, 28, 28, 34),
                      decoration: const BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                          colors: [Color(0xFF1A7A6C), AppTheme.panelBg, Color(0xFF082E29)],
                        ),
                      ),
                      child: const _BrandPanel(),
                    ),
                  ),
                Expanded(
                  flex: 9,
                  child: Align(
                    alignment: Alignment.topCenter,
                    child: SingleChildScrollView(
                      padding: EdgeInsets.fromLTRB(
                        24,
                        isWide ? 36 : 22,
                        24,
                        24 + media.viewInsets.bottom,
                      ),
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 430),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (!isWide) const _MobileLogo(),
                            if (!isWide) const SizedBox(height: 20),
                            Align(
                              alignment: Alignment.centerLeft,
                              child: TextButton.icon(
                                onPressed: () => context.go('/login'),
                                icon: const Icon(Icons.arrow_back_rounded, size: 18),
                                label: const Text('Volver al inicio de sesión'),
                                style: TextButton.styleFrom(
                                  foregroundColor: AppTheme.accentDark,
                                  padding: EdgeInsets.zero,
                                ),
                              ),
                            ),
                            const SizedBox(height: 12),
                            Text(
                              'Crear cuenta',
                              style: theme.textTheme.headlineMedium?.copyWith(fontSize: 40),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Completa el formulario para registrarte en SITUR-SMART',
                              style: theme.textTheme.bodyLarge?.copyWith(color: AppTheme.textSecondary),
                            ),
                            const SizedBox(height: 20),
                            Form(
                              key: _formKey,
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  if (_errorMessage != null) ...[
                                    Text(_errorMessage!, style: const TextStyle(color: Colors.red)),
                                    const SizedBox(height: 16),
                                  ],
                                  _label('Nombres'),
                                  const SizedBox(height: 8),
                                  TextFormField(
                                    controller: _nombresController,
                                    textInputAction: TextInputAction.next,
                                    textCapitalization: TextCapitalization.words,
                                    decoration: const InputDecoration(
                                      hintText: 'Juan Carlos',
                                      suffixIcon: Icon(Icons.person_outline),
                                    ),
                                    validator: (value) {
                                      if (value == null || value.trim().isEmpty) {
                                        return 'Los nombres son obligatorios.';
                                      }
                                      return null;
                                    },
                                  ),
                                  const SizedBox(height: 16),
                                  _label('Apellidos'),
                                  const SizedBox(height: 8),
                                  TextFormField(
                                    controller: _apellidosController,
                                    textInputAction: TextInputAction.next,
                                    textCapitalization: TextCapitalization.words,
                                    decoration: const InputDecoration(
                                      hintText: 'García Rojas',
                                      suffixIcon: Icon(Icons.person_outline),
                                    ),
                                    validator: (value) {
                                      if (value == null || value.trim().isEmpty) {
                                        return 'Los apellidos son obligatorios.';
                                      }
                                      return null;
                                    },
                                  ),
                                  const SizedBox(height: 16),
                                  _label('Teléfono (opcional)'),
                                  const SizedBox(height: 8),
                                  TextFormField(
                                    controller: _telefonoController,
                                    keyboardType: TextInputType.phone,
                                    textInputAction: TextInputAction.next,
                                    decoration: const InputDecoration(
                                      hintText: '+591 70000000',
                                      suffixIcon: Icon(Icons.phone_outlined),
                                    ),
                                    validator: (value) {
                                      if (value != null && value.trim().length > 30) {
                                        return 'Máximo 30 caracteres.';
                                      }
                                      return null;
                                    },
                                  ),
                                  const SizedBox(height: 16),
                                  const Text(
                                    'Correo electrónico',
                                    style: TextStyle(
                                      fontSize: 15,
                                      color: AppTheme.labelColor,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  TextFormField(
                                    controller: _emailController,
                                    keyboardType: TextInputType.emailAddress,
                                    textInputAction: TextInputAction.next,
                                    decoration: const InputDecoration(
                                      hintText: 'juan@ejemplo.com',
                                      suffixIcon: Icon(Icons.mail_outline),
                                    ),
                                    validator: (value) {
                                      if (value == null || value.trim().isEmpty) {
                                        return 'El correo es obligatorio.';
                                      }
                                      final emailRegex = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');
                                      if (!emailRegex.hasMatch(value.trim())) {
                                        return 'Ingresa un correo electrónico válido.';
                                      }
                                      return null;
                                    },
                                  ),
                                  const SizedBox(height: 16),
                                  const Text(
                                    'Contraseña',
                                    style: TextStyle(
                                      fontSize: 15,
                                      color: AppTheme.labelColor,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  TextFormField(
                                    controller: _passwordController,
                                    obscureText: _obscurePassword,
                                    textInputAction: TextInputAction.next,
                                    decoration: InputDecoration(
                                      hintText: 'Mínimo 8 caracteres',
                                      suffixIcon: IconButton(
                                        onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
                                        icon: Icon(
                                          _obscurePassword ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                                        ),
                                      ),
                                    ),
                                    validator: (value) {
                                      if (value == null || value.isEmpty) {
                                        return 'La contraseña es obligatoria.';
                                      }
                                      if (value.length < 8) {
                                        return 'La contraseña debe tener al menos 8 caracteres.';
                                      }
                                      return null;
                                    },
                                  ),
                                  const SizedBox(height: 16),
                                  const Text(
                                    'Confirmar contraseña',
                                    style: TextStyle(
                                      fontSize: 15,
                                      color: AppTheme.labelColor,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  TextFormField(
                                    controller: _confirmPasswordController,
                                    obscureText: _obscureConfirmPassword,
                                    textInputAction: TextInputAction.done,
                                    onFieldSubmitted: (_) => _submit(),
                                    decoration: InputDecoration(
                                      hintText: 'Repite tu contraseña',
                                      suffixIcon: IconButton(
                                        onPressed: () => setState(
                                          () => _obscureConfirmPassword = !_obscureConfirmPassword,
                                        ),
                                        icon: Icon(
                                          _obscureConfirmPassword
                                              ? Icons.visibility_outlined
                                              : Icons.visibility_off_outlined,
                                        ),
                                      ),
                                    ),
                                    validator: (value) {
                                      if (value == null || value.isEmpty) {
                                        return 'Debes confirmar la contraseña.';
                                      }
                                      if (value != _passwordController.text) {
                                        return 'Las contraseñas no coinciden.';
                                      }
                                      return null;
                                    },
                                  ),
                                  const SizedBox(height: 24),
                                  SizedBox(
                                    width: double.infinity,
                                    child: DecoratedBox(
                                      decoration: BoxDecoration(
                                        gradient: const LinearGradient(
                                          colors: [AppTheme.accent, AppTheme.accentGradientTo],
                                        ),
                                        borderRadius: BorderRadius.circular(14),
                                      ),
                                      child: ElevatedButton(
                                        onPressed: _isLoading ? null : _submit,
                                        style: ElevatedButton.styleFrom(
                                          backgroundColor: Colors.transparent,
                                          shadowColor: Colors.transparent,
                                          disabledBackgroundColor: Colors.transparent,
                                        ),
                                        child: _isLoading
                                            ? const SizedBox(
                                                height: 20,
                                                width: 20,
                                                child: CircularProgressIndicator(
                                                  strokeWidth: 2.2,
                                                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                                                ),
                                              )
                                            : const Text('Crear cuenta'),
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
            );
          },
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
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          height: 44,
          width: 44,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            color: AppTheme.panelBg,
          ),
          alignment: Alignment.center,
          child: const Icon(Icons.explore, color: AppTheme.accent, size: 22),
        ),
        const SizedBox(width: 10),
        const Text.rich(
          TextSpan(
            children: [
              TextSpan(
                text: 'SITUR',
                style: TextStyle(color: AppTheme.titleColor, fontWeight: FontWeight.w800),
              ),
              TextSpan(
                text: '-SMART',
                style: TextStyle(color: AppTheme.accentDark, fontWeight: FontWeight.w800),
              ),
            ],
          ),
          style: TextStyle(fontSize: 24, letterSpacing: -0.4),
        ),
      ],
    );
  }
}

class _BrandPanel extends StatelessWidget {
  const _BrandPanel();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              height: 44,
              width: 44,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white24),
                color: Colors.white10,
              ),
              alignment: Alignment.center,
              child: const Icon(Icons.explore, color: Colors.white, size: 22),
            ),
            const SizedBox(width: 10),
            const Text(
              'SITUR-SMART',
              style: TextStyle(
                color: Colors.white,
                fontSize: 30,
                fontWeight: FontWeight.w800,
                letterSpacing: -0.6,
              ),
            ),
          ],
        ),
        const Spacer(),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: Colors.white24),
            color: Colors.white10,
          ),
          child: const Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.travel_explore_rounded, color: Colors.white, size: 18),
              SizedBox(width: 10),
              Text(
                'Sistema Inteligente de Turismo',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 28),
        const Text(
          'Gestiona el turismo\nde forma inteligente',
          style: TextStyle(
            color: Colors.white,
            fontSize: 65,
            fontWeight: FontWeight.w800,
            height: 0.9,
            letterSpacing: -1.5,
          ),
        ),
        const SizedBox(height: 24),
        const Text(
          'Plataforma integrada para la administración, análisis y\nseguimiento de destinos turísticos en tiempo real.',
          style: TextStyle(
            color: Colors.white70,
            fontSize: 20,
            height: 1.5,
          ),
        ),
      ],
    );
  }
}
