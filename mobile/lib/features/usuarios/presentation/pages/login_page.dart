import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController(text: 'admin@situr.smart');
  final _passwordController = TextEditingController();

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
    if (!(_formKey.currentState?.validate() ?? false)) return;

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    await Future<void>.delayed(const Duration(milliseconds: 850));
    if (!mounted) return;

    if (_emailController.text.trim().toLowerCase() == 'admin@situr.smart' &&
        _passwordController.text == 'Admin1234') {
      context.go('/home');
      return;
    }

    setState(() {
      _isLoading = false;
      _errorMessage =
          'Credenciales incorrectas. Verifica tu correo y contraseña.';
    });
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
            if (isWide) const Expanded(flex: 11, child: _BrandPanel()),
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
                    constraints: const BoxConstraints(maxWidth: 430),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (!isWide) const _MobileLogo(),
                        if (!isWide) const SizedBox(height: 24),
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
                          _ErrorMessage(message: _errorMessage!),
                        Form(
                          key: _formKey,
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const _FieldLabel('Correo electrónico'),
                              const SizedBox(height: 8),
                              TextFormField(
                                controller: _emailController,
                                keyboardType: TextInputType.emailAddress,
                                textInputAction: TextInputAction.next,
                                decoration: const InputDecoration(
                                  hintText: 'admin@situr.smart',
                                  suffixIcon: Icon(Icons.mail_outline),
                                ),
                                validator: (value) {
                                  if (value == null || value.trim().isEmpty) {
                                    return 'El correo es obligatorio.';
                                  }
                                  if (!RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
                                      .hasMatch(value.trim())) {
                                    return 'Ingresa un correo electrónico válido.';
                                  }
                                  return null;
                                },
                                enabled: !_isLoading,
                              ),
                              const SizedBox(height: 16),
                              const _FieldLabel('Contraseña'),
                              const SizedBox(height: 8),
                              TextFormField(
                                controller: _passwordController,
                                obscureText: _obscurePassword,
                                textInputAction: TextInputAction.done,
                                onFieldSubmitted: (_) {
                                  if (!_isLoading) _submit();
                                },
                                decoration: InputDecoration(
                                  hintText: '••••••••',
                                  suffixIcon: IconButton(
                                    onPressed: _isLoading
                                        ? null
                                        : () => setState(
                                            () => _obscurePassword =
                                                !_obscurePassword,
                                          ),
                                    icon: Icon(
                                      _obscurePassword
                                          ? Icons.visibility_outlined
                                          : Icons.visibility_off_outlined,
                                    ),
                                  ),
                                ),
                                validator: (value) =>
                                    value == null || value.isEmpty
                                    ? 'La contraseña es obligatoria.'
                                    : null,
                                enabled: !_isLoading,
                              ),
                              const SizedBox(height: 14),
                              Row(
                                children: [
                                  Checkbox(
                                    value: _rememberMe,
                                    onChanged: _isLoading
                                        ? null
                                        : (value) => setState(
                                            () => _rememberMe = value ?? false,
                                          ),
                                  ),
                                  const Flexible(
                                    child: Text(
                                      'Recordarme',
                                      style: TextStyle(
                                        fontSize: 14,
                                        color: AppTheme.labelColor,
                                      ),
                                    ),
                                  ),
                                  const Spacer(),
                                  Flexible(
                                    child: TextButton(
                                      onPressed: _isLoading
                                          ? null
                                          : () =>
                                                context.go('/recuperar-password'),
                                      child: const Text(
                                        '¿Olvidaste tu contraseña?',
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 8),
                              SizedBox(
                                width: double.infinity,
                                child: ElevatedButton(
                                  onPressed: _isLoading ? null : _submit,
                                  child: _isLoading
                                      ? const SizedBox(
                                          height: 20,
                                          width: 20,
                                          child: CircularProgressIndicator(
                                            strokeWidth: 2.2,
                                          ),
                                        )
                                      : const Text('Iniciar sesión'),
                                ),
                              ),
                              const SizedBox(height: 12),
                              Align(
                                alignment: Alignment.center,
                                child: TextButton(
                                  onPressed: _isLoading
                                      ? null
                                      : () => context.go('/registrar-usuario'),
                                  child: const Text('¿No tienes una cuenta? Regístrate'),
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
  const _FieldLabel(this.label);
  final String label;

  @override
  Widget build(BuildContext context) => Text(
    label,
    style: const TextStyle(
      fontSize: 15,
      color: AppTheme.labelColor,
      fontWeight: FontWeight.w600,
    ),
  );
}

class _DemoHint extends StatelessWidget {
  const _DemoHint();

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
    decoration: BoxDecoration(
      color: AppTheme.demoBg,
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: AppTheme.demoBorder),
    ),
    child: const Text(
      'Demo: admin@situr.smart / Admin1234',
      style: TextStyle(
        fontSize: 13,
        color: AppTheme.accentDark,
        fontWeight: FontWeight.w600,
      ),
    ),
  );
}

class _ErrorMessage extends StatelessWidget {
  const _ErrorMessage({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    margin: const EdgeInsets.only(bottom: 14),
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(
      color: const Color(0xFFFFF1F2),
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: const Color(0xFFFECACA)),
    ),
    child: Text(
      message,
      style: const TextStyle(
        fontSize: 13,
        color: AppTheme.errorColor,
        fontWeight: FontWeight.w600,
      ),
    ),
  );
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
    return Container(
      padding: const EdgeInsets.all(28),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [Color(0xFF1A7A6C), AppTheme.panelBg, Color(0xFF082E29)],
        ),
      ),
      child: Column(
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
          const SizedBox(height: 30),
          const Row(
            children: [
              _Metric(title: '1.2K+', subtitle: 'Destinos'),
              SizedBox(width: 32),
              _Metric(title: '48K', subtitle: 'Visitantes'),
              SizedBox(width: 32),
              _Metric(title: '99.9%', subtitle: 'Disponibilidad'),
            ],
          ),
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  final String title;
  final String subtitle;

  const _Metric({required this.title, required this.subtitle});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 28,
            fontWeight: FontWeight.w800,
          ),
        ),
        Text(
          subtitle,
          style: const TextStyle(
            color: Colors.white70,
            fontSize: 15,
          ),
        ),
      ],
    );
  }
}
