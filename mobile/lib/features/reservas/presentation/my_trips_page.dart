import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../marketplace/presentation/widgets/marketplace_widgets.dart';
import '../data/booking_models.dart';
import '../data/booking_service.dart';
import 'booking_status_chip.dart';

/// Reservas del turista agrupadas en pendientes, próximas y anteriores.
class MyTripsPage extends StatefulWidget {
  const MyTripsPage({super.key, this.service});

  final BookingService? service;

  @override
  State<MyTripsPage> createState() => _MyTripsPageState();
}

class _MyTripsPageState extends State<MyTripsPage> {
  late final BookingService _service = widget.service ?? BookingService();

  List<Booking> _bookings = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = _bookings.isEmpty;
      _error = null;
    });
    try {
      final bookings = await _service.list();
      if (!mounted) return;
      setState(() {
        _bookings = bookings;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = error is ApiException ? error.message : 'No se pudieron cargar tus viajes.';
      });
    }
  }

  Future<void> _open(Booking booking) async {
    await context.push('/reserva/${booking.id}');
    // Al volver puede haber cambiado de estado (pagada, cancelada).
    if (mounted) _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppTheme.accentDark,
        foregroundColor: Colors.white,
        title: const Text('Mis viajes', style: TextStyle(fontWeight: FontWeight.bold)),
      ),
      body: _body(),
    );
  }

  Widget _body() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return ErrorRetry(message: _error!, onRetry: _load);

    final pending = _bookings.where((b) => b.pendingPayment).toList();
    final upcoming = _bookings.where((b) => b.confirmed).toList()..sort((a, b) => a.start.compareTo(b.start));
    final past = _bookings.where((b) => b.finished || b.inactive).toList();

    if (_bookings.isEmpty) {
      return RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            const SizedBox(height: 120),
            EmptyState(
              icon: Icons.luggage_outlined,
              title: 'Todavía no tienes viajes',
              message: 'Reserva una habitación o un tour y aquí verás tu voucher.',
              action: OutlinedButton(
                onPressed: () => context.go('/explorar'),
                child: const Text('Explorar'),
              ),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          if (pending.isNotEmpty) ..._section('Pendientes de pago', pending),
          if (upcoming.isNotEmpty) ..._section('Próximos', upcoming),
          if (past.isNotEmpty) ..._section('Anteriores', past),
        ],
      ),
    );
  }

  List<Widget> _section(String title, List<Booking> bookings) => [
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 16, 4, 8),
          child: Text(title, style: Theme.of(context).textTheme.titleLarge),
        ),
        for (final booking in bookings)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: _TripCard(booking: booking, onTap: () => _open(booking)),
          ),
      ];
}

class _TripCard extends StatelessWidget {
  const _TripCard({required this.booking, required this.onTap});

  static final DateFormat _format = DateFormat('dd/MM/yyyy');

  final Booking booking;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final dates = booking.isLodging
        ? '${_format.format(booking.start)} → ${_format.format(booking.end)}'
        : _format.format(booking.start);
    return Card(
      margin: EdgeInsets.zero,
      elevation: 0,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: AppTheme.inputBorder),
      ),
      child: InkWell(
        onTap: onTap,
        child: Row(
          children: [
            SizedBox(
              width: 96,
              height: 116,
              child: ProductImage(
                url: booking.imageUrl,
                icon: booking.isLodging ? Icons.hotel_outlined : Icons.landscape_outlined,
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    BookingStatusChip(booking: booking),
                    const SizedBox(height: 6),
                    Text(
                      booking.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.w700, color: AppTheme.titleColor),
                    ),
                    Text(dates, style: const TextStyle(fontSize: 13)),
                    Text(
                      '${booking.code} · ${booking.totalLabel}',
                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
