import 'package:flutter/material.dart';

import '../data/booking_models.dart';

/// Estado de una reserva con un color que se entiende de un vistazo.
class BookingStatusChip extends StatelessWidget {
  const BookingStatusChip({super.key, required this.booking});

  final Booking booking;

  @override
  Widget build(BuildContext context) {
    final (Color background, Color foreground, IconData icon) = switch (booking.status) {
      'CONFIRMADA' || 'PAGO_PARCIAL' => (const Color(0xFFD1FAE5), const Color(0xFF047857), Icons.check_circle),
      'COMPLETADA' => (const Color(0xFFE0E7FF), const Color(0xFF3730A3), Icons.flag),
      'CREADA' => (const Color(0xFFFEF3C7), const Color(0xFF92400E), Icons.schedule),
      _ => (const Color(0xFFF3F4F6), const Color(0xFF4B5563), Icons.block),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: background, borderRadius: BorderRadius.circular(20)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: foreground),
          const SizedBox(width: 4),
          Text(
            booking.statusLabel,
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: foreground),
          ),
        ],
      ),
    );
  }
}
