import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../marketplace/presentation/widgets/marketplace_widgets.dart';
import '../../notificaciones/data/notifications_store.dart';
import '../data/booking_models.dart';
import '../data/booking_service.dart';
import 'booking_status_chip.dart';

/// Una reserva: su estado, el voucher con QR cuando está pagada, y pagar o
/// cancelar mientras está pendiente.
///
/// Mientras espera el pago se consulta sola cada pocos segundos y al volver a
/// la app desde la página de Stripe: el backend concilia con Stripe en cada
/// consulta, así que la confirmación aparece sin que el turista haga nada.
///
/// Al terminar de pagar, la página de Stripe reabre la app aquí con
/// [paymentResult] (`exito` o `cancelado`, del enlace
/// situr-smart://app/reserva/ID?pago=exito) para avisar cómo terminó.
class BookingDetailPage extends StatefulWidget {
  const BookingDetailPage({super.key, required this.bookingId, this.paymentResult, this.service});

  final int bookingId;
  final String? paymentResult;
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
  PaidCancellationResult? _cancellation;
  String? _cancellationKey;
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
      // Se acaba de confirmar: el backend dejo un aviso nuevo en la bandeja.
      if (_booking?.pendingPayment == true && !booking.pendingPayment) {
        NotificationsStore.instance.refresh();
      }
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
      // Recién pagó: el webhook llega en segundos, se consulta más seguido.
      final justPaid = widget.paymentResult == 'exito';
      _poll = Timer(Duration(seconds: justPaid ? 2 : 5), () => _load(silent: true));
    }
  }

  Future<void> _openReceipt() async {
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _working = true);
    try {
      final url = await _service.receiptUrl(widget.bookingId);
      // El navegador del celular abre o descarga el PDF; el enlace va firmado.
      if (!await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication)) {
        messenger.showSnackBar(const SnackBar(content: Text('No se pudo abrir el comprobante.')));
      }
    } catch (error) {
      messenger.showSnackBar(
        SnackBar(content: Text(error is ApiException ? error.message : 'No se pudo obtener el comprobante.')),
      );
    } finally {
      if (mounted) setState(() => _working = false);
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

  Future<void> _cancelPaid() async {
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _working = true);
    try {
      final quote = await _service.cancellationQuote(widget.bookingId);
      if (!mounted) return;
      final reason = await showModalBottomSheet<String>(
        context: context,
        isScrollControlled: true,
        useSafeArea: true,
        builder: (context) => _PaidCancellationSheet(
          quote: quote,
          currencySymbol: _booking!.currencySymbol,
        ),
      );
      if (reason == null || !mounted) return;
      _cancellationKey ??= BookingService.newIdempotencyKey();
      final result = await _service.cancelPaid(
        widget.bookingId,
        reason: reason,
        idempotencyKey: _cancellationKey!,
      );
      if (!mounted) return;
      setState(() => _cancellation = result);
      await _load(silent: true);
      _scheduleCancellationPoll(result);
      NotificationsStore.instance.refresh();
    } catch (error) {
      messenger.showSnackBar(
        SnackBar(
          content: Text(
            error is ApiException
                ? error.message
                : 'No se pudo solicitar la cancelación. Puedes reintentar sin duplicar el reembolso.',
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  void _scheduleCancellationPoll(PaidCancellationResult result) {
    _poll?.cancel();
    if (result.refundStatus != 'SOLICITADO' && result.refundStatus != 'PROCESANDO') return;
    _poll = Timer(const Duration(seconds: 5), _refreshCancellation);
  }

  Future<void> _refreshCancellation() async {
    final key = _cancellationKey;
    if (key == null) return;
    try {
      final result = await _service.cancelPaid(
        widget.bookingId,
        reason: '',
        idempotencyKey: key,
      );
      if (!mounted) return;
      setState(() => _cancellation = result);
      _scheduleCancellationPoll(result);
      if (result.completed) {
        await _load(silent: true);
        NotificationsStore.instance.refresh();
      }
    } catch (_) {
      if (mounted) _poll = Timer(const Duration(seconds: 10), _refreshCancellation);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_booking?.code ?? 'Reserva'),
        // Abierta desde el pago o un aviso no hay pantalla detrás: se vuelve a Viajes.
        leading: Navigator.of(context).canPop()
            ? null
            : IconButton(
                tooltip: 'Mis viajes',
                icon: const Icon(Icons.close),
                onPressed: () => context.go('/viajes'),
              ),
      ),
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
          if (_paymentBanner(booking) case final banner?) ...[banner, const SizedBox(height: 16)],
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
          if (booking.confirmed) ...[
            OutlinedButton.icon(
              onPressed: _working ? null : _cancelPaid,
              icon: const Icon(Icons.event_busy_outlined),
              label: const Text('Consultar cancelación'),
            ),
            const SizedBox(height: 12),
          ],
          if (_cancellation case final cancellation?) ...[
            _CancellationStatus(result: cancellation, currencySymbol: booking.currencySymbol),
            const SizedBox(height: 12),
          ],
          if ((booking.confirmed || booking.finished) && booking.qr != null) ...[
            _Voucher(booking: booking),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: _working ? null : _openReceipt,
              icon: const Icon(Icons.picture_as_pdf_outlined),
              label: const Text('Descargar comprobante'),
            ),
          ],
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

  /// Cómo terminó el pago del que se acaba de volver. Null si no se vino de pagar.
  Widget? _paymentBanner(Booking booking) {
    final result = widget.paymentResult;
    if (result == null) return null;
    final (color, border, icon, text) = switch ((result, booking)) {
      (_, Booking(confirmed: true) || Booking(finished: true)) => (
          const Color(0xFFECFDF5),
          const Color(0xFF6EE7B7),
          Icons.check_circle,
          'Pago realizado. Tu reserva fue confirmada. Te enviamos el comprobante por correo.',
        ),
      ('exito', Booking(pendingPayment: true)) => (
          const Color(0xFFEFF6FF),
          const Color(0xFF93C5FD),
          Icons.hourglass_top,
          'Recibimos tu pago. Estamos confirmando tu reserva…',
        ),
      _ => (
          const Color(0xFFFFFBEB),
          const Color(0xFFFDE68A),
          Icons.info_outline,
          'El pago no se completó. No se cobró nada.',
        ),
    };
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color,
        border: Border.all(color: border),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          Icon(icon, color: AppTheme.accentDark),
          const SizedBox(width: 10),
          Expanded(child: Text(text)),
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

class _PaidCancellationSheet extends StatefulWidget {
  const _PaidCancellationSheet({required this.quote, required this.currencySymbol});

  final CancellationQuote quote;
  final String currencySymbol;

  @override
  State<_PaidCancellationSheet> createState() => _PaidCancellationSheetState();
}

class _PaidCancellationSheetState extends State<_PaidCancellationSheet> {
  final TextEditingController _reason = TextEditingController();

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final quote = widget.quote;
    final currency = widget.currencySymbol;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 20, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Antes de cancelar', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            Text('Se aplicará la política “${quote.policy}” que aceptaste al reservar.'),
            const SizedBox(height: 18),
            _AmountRow(label: 'Total pagado', value: '$currency ${quote.paidAmount}'),
            _AmountRow(label: 'Penalización (${quote.penaltyPercentage}%)', value: '$currency ${quote.penaltyAmount}'),
            _AmountRow(label: 'Recibirás', value: '$currency ${quote.refundAmount}', emphasized: true),
            const SizedBox(height: 14),
            TextField(
              controller: _reason,
              maxLength: 1000,
              maxLines: 2,
              decoration: const InputDecoration(labelText: 'Motivo (opcional)', hintText: 'Cuéntanos por qué cancelas'),
            ),
            const Text('El cupo se liberará cuando Stripe confirme la devolución.', style: TextStyle(fontSize: 12)),
            const SizedBox(height: 18),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.pop(context, _reason.text.trim()),
                child: const Text('Confirmar cancelación'),
              ),
            ),
            SizedBox(
              width: double.infinity,
              child: TextButton(onPressed: () => Navigator.pop(context), child: const Text('Conservar reserva')),
            ),
          ],
        ),
      ),
    );
  }
}

class _AmountRow extends StatelessWidget {
  const _AmountRow({required this.label, required this.value, this.emphasized = false});
  final String label;
  final String value;
  final bool emphasized;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          children: [
            Expanded(child: Text(label)),
            Text(value, style: TextStyle(fontWeight: emphasized ? FontWeight.w800 : FontWeight.w600, color: emphasized ? AppTheme.accentDark : null)),
          ],
        ),
      );
}

class _CancellationStatus extends StatelessWidget {
  const _CancellationStatus({required this.result, required this.currencySymbol});
  final PaidCancellationResult result;
  final String currencySymbol;

  @override
  Widget build(BuildContext context) {
    final (color, icon, title) = result.completed
        ? (const Color(0xFFECFDF5), Icons.check_circle_outline, 'Cancelación y devolución completadas')
        : result.failed
            ? (const Color(0xFFFEF2F2), Icons.error_outline, 'La devolución requiere revisión')
            : (const Color(0xFFEFF6FF), Icons.hourglass_top, 'Estamos procesando tu devolución');
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(14)),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: AppTheme.accentDark),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
                Text('Monto previsto: $currencySymbol ${result.refundAmount}.'),
                if (result.failureReason != null) Text(result.failureReason!, style: const TextStyle(color: Colors.red)),
              ],
            ),
          ),
        ],
      ),
    );
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
