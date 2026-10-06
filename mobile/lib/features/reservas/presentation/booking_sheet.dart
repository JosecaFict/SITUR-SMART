import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../data/booking_models.dart';
import '../data/booking_service.dart';

/// Abre la hoja para reservar un producto. Al terminar lleva a la reserva.
Future<void> showBookingSheet(
  BuildContext context, {
  required int productId,
  required String title,
  required bool isRoom,
  required int maxQuantity,
  required int capacityPerUnit,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => BookingSheet(
      productId: productId,
      title: title,
      isRoom: isRoom,
      maxQuantity: maxQuantity,
      capacityPerUnit: capacityPerUnit,
    ),
  );
}

/// Elegir fechas y cantidad, ver el precio y reservar.
///
/// En una habitación se eligen llegada y salida, habitaciones y huéspedes; en
/// lo demás, un día y personas. Cada cambio vuelve a cotizar con el backend,
/// que es quien sabe el cupo real.
class BookingSheet extends StatefulWidget {
  const BookingSheet({
    super.key,
    required this.productId,
    required this.title,
    required this.isRoom,
    required this.maxQuantity,
    required this.capacityPerUnit,
    this.service,
  });

  final int productId;
  final String title;
  final bool isRoom;

  /// Habitaciones de este tipo, o personas como máximo.
  final int maxQuantity;

  /// Huéspedes por habitación. En lo demás no se usa.
  final int capacityPerUnit;
  final BookingService? service;

  @override
  State<BookingSheet> createState() => _BookingSheetState();
}

class _BookingSheetState extends State<BookingSheet> {
  late final BookingService _service = widget.service ?? BookingService();
  final DateFormat _format = DateFormat('dd/MM/yyyy');

  /// Una por intento de reservar: si el turista reintenta tras un error de
  /// red, el backend devuelve la misma reserva en vez de crear otra.
  String _idempotencyKey = BookingService.newIdempotencyKey();

  DateTimeRange? _range;
  DateTime? _day;
  int _quantity = 1;
  int _guests = 1;

  BookingQuote? _quote;
  String? _quoteError;
  bool _quoting = false;
  bool _booking = false;
  Timer? _debounce;
  int _quoteRequest = 0;

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  bool get _hasDates => widget.isRoom ? _range != null : _day != null;

  BookingRequest get _request => BookingRequest(
        productId: widget.productId,
        start: widget.isRoom ? _range!.start : _day!,
        end: widget.isRoom ? _range!.end : null,
        quantity: _quantity,
        guests: widget.isRoom ? _guests : null,
      );

  void _changed() {
    _idempotencyKey = BookingService.newIdempotencyKey();
    if (!_hasDates) return;
    _debounce?.cancel();
    setState(() {
      _quoting = true;
      _quoteError = null;
    });
    _debounce = Timer(const Duration(milliseconds: 350), _fetchQuote);
  }

  Future<void> _fetchQuote() async {
    final requestId = ++_quoteRequest;
    try {
      final quote = await _service.quote(_request);
      if (!mounted || requestId != _quoteRequest) return;
      setState(() {
        _quote = quote;
        _quoting = false;
      });
    } catch (error) {
      if (!mounted || requestId != _quoteRequest) return;
      setState(() {
        _quote = null;
        _quoting = false;
        _quoteError = error is ApiException ? error.message : 'No se pudo calcular el precio.';
      });
    }
  }

  Future<void> _pickDates() async {
    final today = DateUtils.dateOnly(DateTime.now());
    if (widget.isRoom) {
      final picked = await showDateRangePicker(
        context: context,
        firstDate: today,
        lastDate: today.add(const Duration(days: 365)),
        initialDateRange: _range,
        helpText: 'Llegada y salida',
        saveText: 'Listo',
      );
      if (picked == null) return;
      if (picked.duration.inDays < 1) {
        setState(() => _quoteError = 'La salida debe ser al menos un día después de la llegada.');
        return;
      }
      setState(() => _range = picked);
    } else {
      final picked = await showDatePicker(
        context: context,
        firstDate: today,
        lastDate: today.add(const Duration(days: 365)),
        initialDate: _day ?? today,
        helpText: 'Fecha',
      );
      if (picked == null) return;
      setState(() => _day = picked);
    }
    _changed();
  }

  void _setQuantity(int value) {
    setState(() {
      _quantity = value;
      if (widget.isRoom) {
        _guests = _guests.clamp(value, value * widget.capacityPerUnit);
      }
    });
    _changed();
  }

  void _setGuests(int value) {
    setState(() => _guests = value);
    _changed();
  }

  Future<void> _book() async {
    final router = GoRouter.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    setState(() => _booking = true);
    try {
      final booking = await _service.create(_request, idempotencyKey: _idempotencyKey);
      navigator.pop();
      router.push('/reserva/${booking.id}');
      final url = booking.checkoutUrl;
      if (url != null && !await BookingService.openCheckout(url)) {
        messenger.showSnackBar(
          const SnackBar(content: Text('No se pudo abrir la página de pago. Usa el botón "Pagar ahora".')),
        );
      }
    } catch (error) {
      if (!mounted) return;
      setState(() => _booking = false);
      messenger.showSnackBar(
        SnackBar(content: Text(error is ApiException ? error.message : 'No se pudo completar la reserva.')),
      );
      // El cupo pudo cambiar: se vuelve a cotizar.
      if (error is ApiException && error.statusCode == 409) _changed();
    }
  }

  @override
  Widget build(BuildContext context) {
    final dateLabel = !_hasDates
        ? (widget.isRoom ? 'Elegir llegada y salida' : 'Elegir fecha')
        : widget.isRoom
            ? '${_format.format(_range!.start)} → ${_format.format(_range!.end)}'
            : _format.format(_day!);
    final quote = _quote;

    return Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, MediaQuery.viewInsetsOf(context).bottom + 20),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Reservar', style: Theme.of(context).textTheme.titleLarge),
            Text(widget.title, maxLines: 2, overflow: TextOverflow.ellipsis),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: _booking ? null : _pickDates,
              icon: const Icon(Icons.calendar_month_outlined),
              label: Text(dateLabel),
              style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(52)),
            ),
            const SizedBox(height: 12),
            _Stepper(
              label: widget.isRoom ? 'Habitaciones' : 'Personas',
              value: _quantity,
              min: 1,
              max: widget.maxQuantity,
              onChanged: _booking ? null : _setQuantity,
            ),
            if (widget.isRoom)
              _Stepper(
                label: 'Huéspedes',
                value: _guests,
                min: _quantity,
                max: _quantity * widget.capacityPerUnit,
                onChanged: _booking ? null : _setGuests,
              ),
            const SizedBox(height: 12),
            if (_quoting)
              const Padding(
                padding: EdgeInsets.all(12),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_quoteError != null)
              Text(_quoteError!, style: const TextStyle(color: AppTheme.errorColor))
            else if (quote != null)
              _QuoteBox(quote: quote, isRoom: widget.isRoom, quantity: _quantity),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: (quote != null && quote.available && !_quoting && !_booking) ? _book : null,
              child: _booking
                  ? const SizedBox(
                      height: 22,
                      width: 22,
                      child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white),
                    )
                  : const Text('Reservar y pagar'),
            ),
            const SizedBox(height: 8),
            const Text(
              'Pagas con tarjeta en la página segura de Stripe. Tu cupo queda apartado mientras pagas.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }
}

class _QuoteBox extends StatelessWidget {
  const _QuoteBox({required this.quote, required this.isRoom, required this.quantity});

  final BookingQuote quote;
  final bool isRoom;
  final int quantity;

  @override
  Widget build(BuildContext context) {
    final nights = quote.nights ?? 1;
    final detail = isRoom
        ? '${quote.currencySymbol} ${quote.unitPrice} × $quantity ${quantity == 1 ? 'habitación' : 'habitaciones'}'
            ' × $nights ${nights == 1 ? 'noche' : 'noches'}'
        : '${quote.currencySymbol} ${quote.unitPrice} × $quantity ${quantity == 1 ? 'persona' : 'personas'}';
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: quote.available ? AppTheme.demoBg : const Color(0xFFFEF2F2),
        border: Border.all(color: quote.available ? AppTheme.demoBorder : const Color(0xFFFECACA)),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(detail, style: const TextStyle(fontSize: 13)),
          const SizedBox(height: 4),
          Text(
            'Total ${quote.currencySymbol} ${quote.total}',
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: AppTheme.accentDark),
          ),
          const SizedBox(height: 4),
          Text(
            quote.available
                ? 'Disponible'
                : quote.remaining == 0
                    ? 'No quedan cupos para esas fechas.'
                    : 'Solo quedan ${quote.remaining} para esas fechas.',
            style: TextStyle(
              fontWeight: FontWeight.w600,
              color: quote.available ? const Color(0xFF047857) : AppTheme.errorColor,
            ),
          ),
        ],
      ),
    );
  }
}

class _Stepper extends StatelessWidget {
  const _Stepper({
    required this.label,
    required this.value,
    required this.min,
    required this.max,
    required this.onChanged,
  });

  final String label;
  final int value;
  final int min;
  final int max;
  final ValueChanged<int>? onChanged;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(child: Text(label, style: const TextStyle(fontSize: 16, color: AppTheme.labelColor))),
        IconButton.outlined(
          tooltip: 'Menos',
          onPressed: onChanged != null && value > min ? () => onChanged!(value - 1) : null,
          icon: const Icon(Icons.remove),
        ),
        SizedBox(
          width: 40,
          child: Text('$value', textAlign: TextAlign.center, style: const TextStyle(fontSize: 18)),
        ),
        IconButton.outlined(
          tooltip: 'Más',
          onPressed: onChanged != null && value < max ? () => onChanged!(value + 1) : null,
          icon: const Icon(Icons.add),
        ),
      ],
    );
  }
}
