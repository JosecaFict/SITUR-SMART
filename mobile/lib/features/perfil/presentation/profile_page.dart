import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../marketplace/presentation/widgets/marketplace_widgets.dart';
import '../../usuarios/data/auth_service.dart';
import '../data/profile_service.dart';

/// Mi Perfil del turista: ver y editar sus datos, y cerrar sesión.
class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  static const _documentTypes = ['CI', 'Pasaporte', 'Otro'];

  final ProfileService _service = ProfileService();
  final _formKey = GlobalKey<FormState>();
  final _nombres = TextEditingController();
  final _apellidos = TextEditingController();
  final _telefono = TextEditingController();
  final _numeroDocumento = TextEditingController();

  Map<String, dynamic>? _user;
  String? _tipoDocumento;
  DateTime? _fechaNacimiento;
  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _nombres.dispose();
    _apellidos.dispose();
    _telefono.dispose();
    _numeroDocumento.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final user = await _service.me();
      if (!mounted) return;
      _fill(user);
      setState(() => _loading = false);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = error is ApiException ? error.message : 'No se pudo cargar tu perfil.';
      });
    }
  }

  void _fill(Map<String, dynamic> user) {
    final profile = user['perfil'] is Map<String, dynamic> ? user['perfil'] as Map<String, dynamic> : null;
    _user = user;
    _nombres.text = user['nombres']?.toString() ?? '';
    _apellidos.text = user['apellidos']?.toString() ?? '';
    _telefono.text = user['telefono']?.toString() ?? '';
    _numeroDocumento.text = profile?['numero_documento']?.toString() ?? '';
    final tipo = profile?['tipo_documento']?.toString();
    // Un tipo cargado desde la web que no está en la lista se conserva igual.
    _tipoDocumento = (tipo == null || tipo.isEmpty) ? null : tipo;
    final birth = profile?['fecha_nacimiento']?.toString();
    _fechaNacimiento = birth == null ? null : DateTime.tryParse(birth);
  }

  Future<void> _pickBirthDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _fechaNacimiento ?? DateTime(now.year - 25),
      firstDate: DateTime(1900),
      lastDate: now,
      helpText: 'Fecha de nacimiento',
    );
    if (picked != null) setState(() => _fechaNacimiento = picked);
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    FocusScope.of(context).unfocus();
    setState(() => _saving = true);
    try {
      final user = await _service.update(
        nombres: _nombres.text,
        apellidos: _apellidos.text,
        telefono: _telefono.text,
        tipoDocumento: _tipoDocumento,
        numeroDocumento: _numeroDocumento.text,
        fechaNacimiento: _fechaNacimiento,
      );
      if (!mounted) return;
      setState(() {
        _fill(user);
        _saving = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Tus datos se guardaron.')),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(error is ApiException ? error.message : 'No se pudieron guardar los cambios.'),
        ),
      );
    }
  }

  Future<void> _logout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cerrar sesión'),
        content: const Text('¿Quieres cerrar tu sesión en este dispositivo?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancelar')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Cerrar sesión')),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final router = GoRouter.of(context);
    await AuthService().logout();
    router.go('/login');
  }

  String? _required(String? value) =>
      (value == null || value.trim().isEmpty) ? 'Este campo es obligatorio.' : null;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppTheme.accentDark,
        foregroundColor: Colors.white,
        title: const Text('Mi Perfil', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(tooltip: 'Cerrar sesión', onPressed: _logout, icon: const Icon(Icons.logout)),
        ],
      ),
      body: _body(),
    );
  }

  Widget _body() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return ErrorRetry(message: _error!, onRetry: _load);

    final user = _user!;
    final fullName = '${user['nombres'] ?? ''} ${user['apellidos'] ?? ''}'.trim();
    final initials = fullName
        .split(RegExp(r'\s+'))
        .where((part) => part.isNotEmpty)
        .take(2)
        .map((part) => part[0].toUpperCase())
        .join();
    final types = {..._documentTypes, ?_tipoDocumento};

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Center(
            child: CircleAvatar(
              radius: 40,
              backgroundColor: AppTheme.accent,
              child: Text(
                initials.isEmpty ? '?' : initials,
                style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Center(child: Text(fullName, style: Theme.of(context).textTheme.titleLarge)),
          Center(child: Text(user['email']?.toString() ?? '')),
          const SizedBox(height: 24),
          Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text('Datos personales', style: TextStyle(fontWeight: FontWeight.w700, color: AppTheme.labelColor)),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _nombres,
                  textCapitalization: TextCapitalization.words,
                  decoration: const InputDecoration(labelText: 'Nombres'),
                  validator: _required,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _apellidos,
                  textCapitalization: TextCapitalization.words,
                  decoration: const InputDecoration(labelText: 'Apellidos'),
                  validator: _required,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _telefono,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(labelText: 'Teléfono (opcional)'),
                ),
                const SizedBox(height: 12),
                InkWell(
                  onTap: _pickBirthDate,
                  borderRadius: BorderRadius.circular(14),
                  child: InputDecorator(
                    decoration: InputDecoration(
                      labelText: 'Fecha de nacimiento (opcional)',
                      suffixIcon: _fechaNacimiento == null
                          ? const Icon(Icons.calendar_today_outlined)
                          : IconButton(
                              tooltip: 'Quitar fecha',
                              icon: const Icon(Icons.close),
                              onPressed: () => setState(() => _fechaNacimiento = null),
                            ),
                    ),
                    child: Text(
                      _fechaNacimiento == null
                          ? 'Sin especificar'
                          : DateFormat('dd/MM/yyyy').format(_fechaNacimiento!),
                    ),
                  ),
                ),
                const SizedBox(height: 24),
                const Text('Documento de identidad', style: TextStyle(fontWeight: FontWeight.w700, color: AppTheme.labelColor)),
                const SizedBox(height: 12),
                DropdownButtonFormField<String?>(
                  initialValue: _tipoDocumento,
                  decoration: const InputDecoration(labelText: 'Tipo de documento'),
                  items: [
                    const DropdownMenuItem<String?>(value: null, child: Text('Sin especificar')),
                    for (final type in types) DropdownMenuItem<String?>(value: type, child: Text(type)),
                  ],
                  onChanged: (value) => setState(() => _tipoDocumento = value),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _numeroDocumento,
                  decoration: const InputDecoration(labelText: 'Número de documento'),
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: _saving ? null : _save,
                  child: _saving
                      ? const SizedBox(
                          height: 22,
                          width: 22,
                          child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white),
                        )
                      : const Text('Guardar cambios'),
                ),
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  onPressed: () => context.push('/recuperar-password'),
                  icon: const Icon(Icons.lock_reset),
                  label: const Text('Cambiar contraseña'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
