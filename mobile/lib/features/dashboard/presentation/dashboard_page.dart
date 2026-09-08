import 'package:flutter/material.dart';

import '../../../core/storage/token_storage.dart';
import '../../../core/theme/app_theme.dart';

import '../../tenants/data/tenant_service.dart';
import '../../tenants/models/tenant.dart';


/// Dashboard principal del sistema SITUR-SMART.
///
/// Este widget solamente contiene el contenido interno.
/// La estructura general (AppBar, Drawer y navegación)
/// pertenece a MainShellPage.
class DashboardPage extends StatefulWidget {

  const DashboardPage({
    super.key,
  });


  @override
  State<DashboardPage> createState() =>
      _DashboardPageState();

}



/// Controla la carga de información del usuario
/// y las empresas asociadas.
class _DashboardPageState extends State<DashboardPage> {

  final TokenStorage _storage =
      TokenStorage();

  final TenantService _tenantService =
      TenantService();


  List<Tenant> _tenants = [];

  String _name = 'Usuario';

  String _role = '';


  bool _loading = true;

  String? _error;



  @override
  void initState() {

    super.initState();

    _loadData();

  }



  /// Obtiene datos reales almacenados
  /// y empresas desde el servicio existente.
  Future<void> _loadData() async {

    try {

      final user =
          await _storage.getUser();


      final tenants =
          await _tenantService.getTenants();


      setState(() {

        _tenants = tenants;

        _name =
            '${user?['nombres'] ?? ''} ${user?['apellidos'] ?? ''}'
                .trim();

        _role =
            user?['rol'] ?? '';

        _loading = false;

      });


    } catch (e) {

      setState(() {

        _error = e.toString();

        _loading = false;

      });

    }

  }



  @override
  Widget build(BuildContext context) {

    if (_loading) {

      return const Center(
        child: CircularProgressIndicator(),
      );

    }


    if (_error != null) {

      return Center(
        child: Text(_error!),
      );

    }


    return RefreshIndicator(

      onRefresh: _loadData,


      child: ListView(

        padding:
            const EdgeInsets.all(20),


        children: [


          _welcomeCard(),


          const SizedBox(
            height: 20,
          ),


          Row(

            children: [

              Expanded(
                child: _quickAction(
                  Icons.business,
                  'Nueva empresa',
                ),
              ),

              const SizedBox(
                width: 12,
              ),

              Expanded(
                child: _quickAction(
                  Icons.history,
                  'Auditoría',
                ),
              ),

            ],

          ),


          const SizedBox(
            height: 24,
          ),


          const Text(
            'Resumen general',
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.bold,
            ),
          ),


          const SizedBox(
            height: 15,
          ),


          Row(

            children: [

              Expanded(
                child: _statCard(
                  'Empresas',
                  '${_tenants.length}',
                  Icons.business,
                ),
              ),

              const SizedBox(
                width: 12,
              ),

              Expanded(
                child: _statCard(
                  'Activas',
                  '${_tenants.length}',
                  Icons.check_circle,
                ),
              ),

            ],

          ),


          const SizedBox(
            height: 24,
          ),


          const Text(
            'Empresas registradas recientemente',
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.bold,
            ),
          ),


          const SizedBox(
            height: 12,
          ),


          ..._tenants.map(
            (tenant) => _tenantCard(tenant),
          ),


          const SizedBox(
            height: 24,
          ),


          _platformCard(),

        ],

      ),

    );

  }



  /// Tarjeta de bienvenida del usuario.
  Widget _welcomeCard() {

    return Container(

      padding:
          const EdgeInsets.all(20),


      decoration:
          BoxDecoration(

        color:
            AppTheme.panelBg,

        borderRadius:
            BorderRadius.circular(18),

      ),


      child: Column(

        crossAxisAlignment:
            CrossAxisAlignment.start,


        children: [

          const Text(
            'Bienvenido',
            style: TextStyle(
              color: Colors.white70,
            ),
          ),


          Text(
            _name,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 25,
              fontWeight: FontWeight.bold,
            ),
          ),


          Text(
            _role,
            style: const TextStyle(
              color: Colors.white70,
            ),
          ),

        ],

      ),

    );

  }



  /// Botón de acción rápida.
  Widget _quickAction(
    IconData icon,
    String text,
  ) {

    return Container(

      height:
          55,

      decoration:
          BoxDecoration(

        color:
            AppTheme.accent,

        borderRadius:
            BorderRadius.circular(14),

      ),

      child:
          Center(

        child:
            Row(

          mainAxisAlignment:
              MainAxisAlignment.center,

          children: [

            Icon(
              icon,
              color: Colors.white,
            ),

            const SizedBox(
              width: 8,
            ),

            Text(
              text,
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
              ),
            ),

          ],

        ),

      ),

    );

  }



  /// Tarjeta estadística del dashboard.
  Widget _statCard(
    String title,
    String value,
    IconData icon,
  ) {

    return Container(

      padding:
          const EdgeInsets.all(16),

      decoration:
          BoxDecoration(

        color:
            Colors.white,

        borderRadius:
            BorderRadius.circular(16),

        border:
            Border.all(
              color: AppTheme.demoBorder,
            ),

      ),


      child:
          Column(

        crossAxisAlignment:
            CrossAxisAlignment.start,

        children: [

          Icon(
            icon,
            color: AppTheme.accentDark,
          ),

          const SizedBox(
            height: 10,
          ),

          Text(
            value,
            style: const TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),

          Text(title),

        ],

      ),

    );

  }



  /// Tarjeta de empresa.
  Widget _tenantCard(
    Tenant tenant,
  ) {

    return Container(

      margin:
          const EdgeInsets.only(
            bottom: 12,
          ),

      padding:
          const EdgeInsets.all(16),

      decoration:
          BoxDecoration(

        color:
            Colors.white,

        borderRadius:
            BorderRadius.circular(16),

        border:
            Border.all(
              color: AppTheme.demoBorder,
            ),

      ),


      child:
          ListTile(

        leading:
            const Icon(
              Icons.business,
              color: AppTheme.accentDark,
            ),

        title:
            Text(
              tenant.nombreComercial,
              style: const TextStyle(
                fontWeight: FontWeight.bold,
              ),
            ),

        subtitle:
            Text(
              tenant.razonSocial,
            ),

      ),

    );

  }



  /// Bloque informativo de plataforma.
  Widget _platformCard() {

    return Container(

      padding:
          const EdgeInsets.all(18),

      decoration:
          BoxDecoration(

        color:
            AppTheme.demoBg,

        borderRadius:
            BorderRadius.circular(18),

        border:
            Border.all(
              color: AppTheme.demoBorder,
            ),

      ),

      child:
          const Column(

        crossAxisAlignment:
            CrossAxisAlignment.start,

        children: [

          Text(
            'Acciones de plataforma',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),

          SizedBox(
            height: 8,
          ),

          Text(
            'Administración segura bajo arquitectura multitenant.',
          ),

        ],

      ),

    );

  }

}
