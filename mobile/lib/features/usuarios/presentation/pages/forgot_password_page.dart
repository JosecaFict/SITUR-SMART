import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';

class ForgotPasswordPage extends StatefulWidget {
  const ForgotPasswordPage({super.key});

  @override
  State<ForgotPasswordPage> createState() => _ForgotPasswordPageState();
}

class _ForgotPasswordPageState extends State<ForgotPasswordPage> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  bool _isLoading = false;

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();
    if (!(_formKey.currentState?.validate() ?? false)) {
      return;
    }

    setState(() => _isLoading = true);
    await Future<void>.delayed(const Duration(milliseconds: 800));

    if (!mounted) return;

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Instrucciones enviadas. Revisa tu correo electrónico.'),
      ),
    );
    setState(() => _isLoading = false);
    context.go('/login');
  }

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
                            const SizedBox(height: 16),
                            Center(
                              child: Container(
                                width: 64,
                                height: 64,
                                decoration: BoxDecoration(
                                  color: const Color(0xFFE0F7F4),
                                  borderRadius: BorderRadius.circular(18),
                                ),
                                child: const Icon(Icons.mail_outline_rounded, size: 30, color: AppTheme.accentDark),
                              ),
                            ),
                            const SizedBox(height: 18),
                            Text(
                              'Recuperar contraseña',
                              style: theme.textTheme.headlineMedium?.copyWith(fontSize: 40),
                              textAlign: TextAlign.left,
                            ),
                            const SizedBox(height: 10),
                            Text(
                              'Ingresa tu correo y te enviaremos instrucciones de recuperación.',
                              style: theme.textTheme.bodyLarge?.copyWith(color: AppTheme.textSecondary),
                            ),
                            const SizedBox(height: 22),
                            Form(
                              key: _formKey,
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
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
                                    autofillHints: const [AutofillHints.email],
                                    decoration: const InputDecoration(
                                      hintText: 'tu@correo.com',
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
                                            : const Text('Enviar instrucciones'),
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
