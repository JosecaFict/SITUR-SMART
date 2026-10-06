import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../data/auth_service.dart';

/// Recuperación de contraseña en tres pasos, igual que en la web:
/// correo -> código de 6 dígitos enviado por correo -> nueva contraseña.
class ForgotPasswordPage extends StatefulWidget {
  const ForgotPasswordPage({super.key});

  @override
  State<ForgotPasswordPage> createState() => _ForgotPasswordPageState();
}

enum _Step { email, code, password }

class _ForgotPasswordPageState extends State<ForgotPasswordPage> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _codeController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmController = TextEditingController();
  final AuthService _authService = AuthService();

  _Step _step = _Step.email;
  bool _isLoading = false;
  bool _obscurePassword = true;
  String? _errorMessage;
  String? _infoMessage;

  static final _emailRegex = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');
  static final _codeRegex = RegExp(r'^\d{6}$');

  String get _email => _emailController.text.trim().toLowerCase();

  @override
  void dispose() {
    _emailController.dispose();
    _codeController.dispose();
    _passwordController.dispose();
    _confirmController.dispose();
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
      switch (_step) {
        case _Step.email:
          {
            final message = await _authService.requestPasswordReset(_email);
            if (!mounted) return;
            setState(() {
              _infoMessage = message;
              _step = _Step.code;
            });
          }
        case _Step.code:
          {
            await _authService.verifyPasswordResetCode(
              email: _email,
              code: _codeController.text.trim(),
            );
            if (!mounted) return;
            setState(() {
              _infoMessage = 'Código verificado. Ahora elige tu nueva contraseña.';
              _step = _Step.password;
            });
          }
        case _Step.password:
          {
            final message = await _authService.confirmPasswordReset(
              email: _email,
              code: _codeController.text.trim(),
              newPassword: _passwordController.text,
            );
            if (!mounted) return;
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
            context.go('/login');
          }
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _errorMessage = e.toString());
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _resendCode() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final message = await _authService.requestPasswordReset(_email);
      if (!mounted) return;
      setState(() => _infoMessage = message);
    } catch (e) {
      if (!mounted) return;
      // El backend limita a un código por minuto y lo explica en el mensaje.
      setState(() => _errorMessage = e.toString());
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _changeEmail() {
    setState(() {
      _step = _Step.email;
      _codeController.clear();
      _passwordController.clear();
      _confirmController.clear();
      _errorMessage = null;
      _infoMessage = null;
    });
  }

  String get _subtitle => switch (_step) {
        _Step.email => 'Ingresa tu correo y te enviaremos un código de verificación de 6 dígitos.',
        _Step.code => 'Revisa tu correo e ingresa el código de 6 dígitos que te enviamos.',
        _Step.password => 'Elige una contraseña nueva de al menos 8 caracteres.',
      };

  String get _buttonText => switch (_step) {
        _Step.email => 'Enviar código',
        _Step.code => 'Verificar código',
        _Step.password => 'Cambiar contraseña',
      };

  Widget _label(String text) => Text(
        text,
        style: const TextStyle(
          fontSize: 15,
          color: AppTheme.labelColor,
          fontWeight: FontWeight.w600,
        ),
      );

  List<Widget> _fields() {
    switch (_step) {
      case _Step.email:
        return [
          _label('Correo electrónico'),
          const SizedBox(height: 8),
          TextFormField(
            controller: _emailController,
            keyboardType: TextInputType.emailAddress,
            autofillHints: const [AutofillHints.email],
            textInputAction: TextInputAction.done,
            onFieldSubmitted: (_) => _submit(),
            decoration: const InputDecoration(
              hintText: 'tu@correo.com',
              suffixIcon: Icon(Icons.mail_outline),
            ),
            validator: (value) {
              if (value == null || value.trim().isEmpty) {
                return 'El correo es obligatorio.';
              }
              if (!_emailRegex.hasMatch(value.trim())) {
                return 'Ingresa un correo electrónico válido.';
              }
              return null;
            },
          ),
        ];
      case _Step.code:
        return [
          _label('Código de verificación'),
          const SizedBox(height: 8),
          TextFormField(
            controller: _codeController,
            keyboardType: TextInputType.number,
            maxLength: 6,
            autofillHints: const [AutofillHints.oneTimeCode],
            textInputAction: TextInputAction.done,
            onFieldSubmitted: (_) => _submit(),
            decoration: const InputDecoration(
              hintText: '000000',
              counterText: '',
              suffixIcon: Icon(Icons.pin_outlined),
            ),
            validator: (value) {
              if (value == null || !_codeRegex.hasMatch(value.trim())) {
                return 'El código tiene exactamente 6 dígitos.';
              }
              return null;
            },
          ),
          const SizedBox(height: 4),
          Wrap(
            children: [
              TextButton(
                onPressed: _isLoading ? null : _resendCode,
                child: const Text('Reenviar código'),
              ),
              TextButton(
                onPressed: _isLoading ? null : _changeEmail,
                child: const Text('Cambiar correo'),
              ),
            ],
          ),
        ];
      case _Step.password:
        return [
          _label('Nueva contraseña'),
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
              if (value == null || value.length < 8) {
                return 'La contraseña debe tener al menos 8 caracteres.';
              }
              return null;
            },
          ),
          const SizedBox(height: 16),
          _label('Confirmar contraseña'),
          const SizedBox(height: 8),
          TextFormField(
            controller: _confirmController,
            obscureText: _obscurePassword,
            textInputAction: TextInputAction.done,
            onFieldSubmitted: (_) => _submit(),
            decoration: const InputDecoration(
              hintText: 'Repite tu contraseña',
            ),
            validator: (value) {
              if (value != _passwordController.text) {
                return 'Las contraseñas no coinciden.';
              }
              return null;
            },
          ),
        ];
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
                        TextButton.icon(
                          onPressed: () => context.go('/login'),
                          icon: const Icon(Icons.arrow_back_rounded, size: 18),
                          label: const Text('Volver al inicio de sesión'),
                          style: TextButton.styleFrom(
                            foregroundColor: AppTheme.accentDark,
                            padding: EdgeInsets.zero,
                          ),
                        ),
                        const SizedBox(height: 16),
                        Center(
                          child: Container(
                            width: 64,
                            height: 64,
                            decoration: BoxDecoration(
                              color: const Color(0xFFE0F7F4),
                              borderRadius: BorderRadius.circular(18),
                            ),
                            child: Icon(
                              _step == _Step.password ? Icons.lock_reset_rounded : Icons.mail_outline_rounded,
                              size: 30,
                              color: AppTheme.accentDark,
                            ),
                          ),
                        ),
                        const SizedBox(height: 18),
                        Text(
                          'Recuperar contraseña',
                          style: theme.textTheme.headlineMedium?.copyWith(fontSize: 40),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'Paso ${_step.index + 1} de 3',
                          style: theme.textTheme.labelLarge?.copyWith(color: AppTheme.accentDark),
                        ),
                        const SizedBox(height: 10),
                        Text(
                          _subtitle,
                          style: theme.textTheme.bodyLarge?.copyWith(color: AppTheme.textSecondary),
                        ),
                        if (_step != _Step.email) ...[
                          const SizedBox(height: 6),
                          Text(_email, style: const TextStyle(fontWeight: FontWeight.w600)),
                        ],
                        const SizedBox(height: 22),
                        if (_infoMessage != null && _errorMessage == null) ...[
                          Text(_infoMessage!, style: const TextStyle(color: AppTheme.accentDark)),
                          const SizedBox(height: 16),
                        ],
                        if (_errorMessage != null) ...[
                          Text(_errorMessage!, style: const TextStyle(color: Colors.red)),
                          const SizedBox(height: 16),
                        ],
                        Form(
                          key: _formKey,
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              ..._fields(),
                              const SizedBox(height: 20),
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
                                        : Text(_buttonText),
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
