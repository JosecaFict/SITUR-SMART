import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../data/payment_models.dart';
import '../data/payment_service.dart';

class MyPaymentsPage extends StatefulWidget {
  const MyPaymentsPage({super.key, this.service});
  final PaymentService? service;

  @override
  State<MyPaymentsPage> createState() => _MyPaymentsPageState();
}

class _MyPaymentsPageState extends State<MyPaymentsPage> {
  late final PaymentService _service = widget.service ?? PaymentService();
  List<PaymentMovement> _items = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    setState(() { _loading = _items.isEmpty; _error = null; });
    try { final items = await _service.mine(); if (mounted) setState(() { _items = items; _loading = false; }); }
    catch (error) { if (mounted) setState(() { _loading = false; _error = error is ApiException ? error.message : 'No se pudieron cargar tus pagos.'; }); }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Mis pagos')),
        body: RefreshIndicator(onRefresh: _load, child: _body()),
      );

  Widget _body() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return ListView(children: [const SizedBox(height: 120), Center(child: Text(_error!)), TextButton(onPressed: _load, child: const Text('Reintentar'))]);
    if (_items.isEmpty) return ListView(children: const [SizedBox(height: 140), Icon(Icons.receipt_long_outlined, size: 48), SizedBox(height: 12), Center(child: Text('Todavía no tienes pagos'))]);
    return ListView.separated(
      padding: const EdgeInsets.all(16), itemCount: _items.length, separatorBuilder: (_, _) => const SizedBox(height: 12),
      itemBuilder: (context, index) => _PaymentCard(payment: _items[index]),
    );
  }
}

class _PaymentCard extends StatelessWidget {
  const _PaymentCard({required this.payment});
  final PaymentMovement payment;

  @override
  Widget build(BuildContext context) => InkWell(
        onTap: () => context.push('/reserva/${payment.bookingId}'),
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(color: Colors.white, border: Border.all(color: AppTheme.inputBorder), borderRadius: BorderRadius.circular(16)),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(payment.product, style: const TextStyle(fontWeight: FontWeight.w800, color: AppTheme.titleColor)), Text('${payment.company} · ${payment.bookingCode}', style: const TextStyle(fontSize: 12))])), Text('${payment.currencySymbol} ${payment.amount}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: AppTheme.accentDark))]),
            const SizedBox(height: 8), Text('${DateFormat('dd/MM/yyyy HH:mm').format(payment.createdAt)} · ${_method(payment.method)} · ${_state(payment.status)}', style: const TextStyle(fontSize: 12)),
            for (final refund in payment.refunds) Padding(padding: const EdgeInsets.only(top: 8), child: Text('Reembolso ${_state(refund.status).toLowerCase()}: ${payment.currencySymbol} ${refund.amount}', style: const TextStyle(fontWeight: FontWeight.w600))),
          ]),
        ),
      );

  static String _method(String value) => const {'TARJETA': 'Tarjeta', 'EFECTIVO': 'Efectivo', 'QR': 'QR', 'TRANSFERENCIA': 'Transferencia'}[value] ?? value;
  static String _state(String value) => const {'APROBADO': 'Aprobado', 'PENDIENTE': 'Pendiente', 'ANULADO': 'Anulado', 'COMPLETADO': 'Completado', 'PROCESANDO': 'Procesando', 'FALLIDO': 'Fallido'}[value] ?? value;
}
