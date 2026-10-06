import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../marketplace/presentation/widgets/marketplace_widgets.dart';
import '../data/booking_models.dart';
import '../data/booking_service.dart';
import 'booking_status_chip.dart';

/// Una reserva: su estado, el voucher con QR cuando está pagada, y pagar o
/// cancelar mientras está pendiente.
///
/// Mientras espera el pago se consulta sola cada pocos segundos y al volver a
/// la app desde la página de Stripe: el backend concilia con Stripe en cada
/// consulta, así que la confirmación aparece sin que el turista haga nada.
class BookingDetailPage extends StatefulWidget {
  const BookingDetailPage({super.key, required this.bookingId, this.service});

  final int bookingId;
  final BookingService? service;

  @override
  State<BookingDetailPage> createState() => _BookingDetailPageState();
}

class _BookingDetailPageState extends State<BookingDetailPage> with WidgetsBindingObserver {
  late final BookingService _service = widget.service ?? BookingService();
  final DateFormat _date = DateFormat('EEE d MMM yyyy', 'es');

  Booking? _booking;
  bool _loading = true;
  bool _working = false;
  String? _error;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _poll?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _load(silent: true);
  }

  Future<void> _load({bool silent = false}) async {
    if (!silent) {
      setState(() {
        _loading = _booking == null;
        _error = null;
      });
    }
    try {
      final booking = await _service.detail(widget.bookingId);
      if (!mounted) return;
      setState(() {
        _booking = booking;
        _loading = false;
        _error = null;
      });
      _schedulePoll(booking);
    } catch (error) {
      if (!mounted || silent) return;
      setState(() {
        _loading = false;
        _error = error is ApiException ? error.message : 'No se pudo cargar la reserva.';
      });
    }
  }

  void _schedulePoll(Booking booking) {
    _poll?.cancel();
    if (booking.pendingPayment) {
      _poll = Timer(const Duration(seconds: 5), () => _load(silent: true));
    }
  }

  Future<void> _pay() async {
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _working = true);
    try {
      final url = await _service.checkoutUrl(widget.bookingId);
      if (!await BookingService.openCheckout(url)) {
        messenger.showSnackBar(const SnackBar(content: Text('No se pudo abrir la página de pago.')));
      }
    } catch (error) {
      messenger.showSnackBar(
        SnackBar(content: Text(error is ApiException ? error.message : 'No se pudo abrir el pago.')),
      );
      await _load(silent: true);
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _cancel() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancelar reserva'),
        content: const Text('Todavía no pagaste, así que no se cobrará nada. ¿Liberar el cupo?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Volver')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Cancelar reserva')),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _working = true);
    try {
      final booking = await _service.cancel(widget.bookingId);
      if (!mounted) return;
      setState(() => _booking = booking);
      _schedulePoll(booking);
    } catch (error) {
      messenger.showSnackBar(
        SnackBar(content: Text(error is ApiException ? error.message : 'No se pudo cancelar.')),
      );
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_booking?.code ?? 'Reserva')),
      body: _body(),
    );
  }

  Widget _body() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return ErrorRetry(message: _error!, onRetry: _load);
    final booking = _booking!;

    final dates = booking.isLodging
        ? '${_date.format(booking.start)} → ${_date.format(booking.end)}'
        : _date.format(booking.start);
    final nights = booking.nights;

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Row(children: [BookingStatusChip(booking: booking)]),
          const SizedBox(height: 12),
          Text(
            booking.title,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: AppTheme.titleColor,
                ),
          ),
          if (booking.establishment != null) Text(booking.productName),
          const SizedBox(height: 8),
          InfoLine(icon: Icons.place_outlined, text: booking.city),
          InfoLine(icon: Icons.business_outlined, text: booking.company),
          InfoLine(
            icon: Icons.event_outlined,
            text: nights == null ? dates : '$dates · $nights ${nights == 1 ? 'noche' : 'noches'}',
          ),
          InfoLine(
            icon: booking.isLodging ? Icons.bed_outlined : Icons.people_outline,
            text: '${booking.quantity} ${booking.unit}'
                '${booking.guests != null ? ' · ${booking.guests} ${booking.guests == 1 ? 'huésped' : 'huéspedes'}' : ''}',
          ),
          const SizedBox(height: 20),
          PriceBox(
            label: booking.confirmed || booking.finished ? 'Total pagado' : 'Total',
            price: booking.totalLabel,
          ),
          const SizedBox(height: 20),
          if (booking.pendingPayment) ..._pendingSection(booking),
          if ((booking.confirmed || booking.finished) && booking.qr != null) _Voucher(booking: booking),
          if (booking.inactive)
            const Text(
              'Esta reserva ya no está activa y su cupo quedó libre. No se cobró nada.',
              textAlign: TextAlign.center,
            ),
          const SizedBox(height: 16),
          if (booking.lodgingId != null)
            TextButton(
              onPressed: () => context.push('/hospedaje/${booking.lodgingId}'),
              child: const Text('Ver el hospedaje'),
            )
          else
            TextButton(
              onPressed: () => context.push('/producto/${booking.productId}'),
              child: const Text('Ver el producto'),
            ),
        ],
      ),
    );
  }

  List<Widget> _pendingSection(Booking booking) {
    final expires = booking.expiresAt;
    return [
      Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: const Color(0xFFFFFBEB),
          border: Border.all(color: const Color(0xFFFDE68A)),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Text(
          expires == null
              ? 'Tu cupo está apartado mientras completas el pago.'
              : 'Tu cupo está apartado hasta las ${DateFormat('HH:mm').format(expires)}. '
                  'Si no pagas antes, se libera.',
        ),
      ),
      const SizedBox(height: 16),
      ElevatedButton.icon(
        onPressed: _working ? null : _pay,
        icon: const Icon(Icons.credit_card),
        label: const Text('Pagar ahora'),
      ),
      const SizedBox(height: 8),
      OutlinedButton(
        onPressed: _working ? null : _cancel,
        child: const Text('Cancelar reserva'),
      ),
    ];
  }
}

class _Voucher extends StatelessWidget {
  const _Voucher({required this.booking});

  final Booking booking;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: AppTheme.inputBorder),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          const Text('Tu voucher', style: TextStyle(fontWeight: FontWeight.w700, color: AppTheme.titleColor)),
          const SizedBox(height: 4),
          const Text('Muéstralo al llegar.', style: TextStyle(fontSize: 13)),
          const SizedBox(height: 12),
          QrImageView(
            data: booking.qr!,
            size: 220,
            backgroundColor: Colors.white,
            semanticsLabel: 'Código QR de la reserva ${booking.code}',
          ),
          const SizedBox(height: 8),
          SelectableText(
            booking.code,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800, letterSpacing: 1.5),
          ),
        ],
      ),
    );
  }
}
