import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../data/marketplace_service.dart';
import '../../favoritos/presentation/favorite_button.dart';
import '../../itinerarios/presentation/add_to_itinerary.dart';
import '../../reservas/presentation/booking_sheet.dart';
import '../models/marketplace_models.dart';
import 'widgets/marketplace_widgets.dart';

/// Ficha pública de un hospedaje con sus tipos de habitación.
class LodgingDetailPage extends StatefulWidget {
  const LodgingDetailPage({super.key, required this.lodgingId, this.service});

  /// Id de establecimiento_hospedaje, no del producto.
  final int lodgingId;
  final MarketplaceService? service;

  @override
  State<LodgingDetailPage> createState() => _LodgingDetailPageState();
}

class _LodgingDetailPageState extends State<LodgingDetailPage> {
  late final MarketplaceService _service = widget.service ?? MarketplaceService();

  Lodging? _lodging;
  List<Room> _rooms = const [];
  bool _loading = true;
  bool _notFound = false;
  String? _error;
  String? _roomsError;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
      _roomsError = null;
      _notFound = false;
    });
    try {
      final lodging = await _service.lodging(widget.lodgingId);
      List<Room> rooms = const [];
      String? roomsError;
      try {
        rooms = await _service.lodgingRooms(widget.lodgingId);
      } catch (_) {
        roomsError = 'No se pudieron cargar las habitaciones.';
      }
      if (!mounted) return;
      setState(() {
        _lodging = lodging;
        _rooms = rooms;
        _roomsError = roomsError;
        _loading = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _notFound = error.statusCode == 404;
        _error = error.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'No se pudo conectar con el servidor. Revisa tu conexión.';
      });
    }
  }

  Future<void> _openMap(Lodging lodging) async {
    final lat = lodging.latitud!;
    final lon = lodging.longitud!;
    final url = Uri.parse('https://www.openstreetmap.org/?mlat=$lat&mlon=$lon#map=17/$lat/$lon');
    final opened = await launchUrl(url, mode: LaunchMode.externalApplication);
    if (!opened && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No se pudo abrir el mapa en este dispositivo.')),
      );
    }
  }

  void _showRoom(Room room) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheetContext) => _RoomSheet(
        room: room,
        onBook: () {
          Navigator.pop(sheetContext);
          showBookingSheet(
            context,
            productId: room.productoId,
            title: '${_lodging!.nombre} · ${room.nombre}',
            isRoom: true,
            maxQuantity: room.cantidad,
            capacityPerUnit: room.capacidadMaxima,
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final lodging = _lodging;
    if (_loading) {
      return Scaffold(appBar: AppBar(), body: const Center(child: CircularProgressIndicator()));
    }
    if (_notFound) {
      return Scaffold(
        appBar: AppBar(),
        body: const EmptyState(
          icon: Icons.hotel_outlined,
          title: 'Este hospedaje no está disponible',
          message: 'Puede que ya no esté publicado.',
        ),
      );
    }
    if (_error != null || lodging == null) {
      return Scaffold(
        appBar: AppBar(),
        body: ErrorRetry(message: _error ?? 'No se pudo cargar el hospedaje.', onRetry: _load),
      );
    }

    final checkIn = shortTime(lodging.horaCheckIn);
    final checkOut = shortTime(lodging.horaCheckOut);
    final schedule = [
      if (checkIn != null) 'Check-in $checkIn',
      if (checkOut != null) 'Check-out $checkOut',
    ].join(' · ');
    final location = [
      if (lodging.localidad != null) lodging.localidad!,
      lodging.ciudad,
      lodging.pais,
    ].join(', ');

    return Scaffold(
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            pinned: true,
            expandedHeight: 240,
            backgroundColor: AppTheme.accentDark,
            foregroundColor: Colors.white,
            actions: [FavoriteButton(productId: lodging.productoId, onImage: true)],
            flexibleSpace: FlexibleSpaceBar(
              background: ProductImage(url: lodging.imagenUrl, icon: Icons.hotel_outlined),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
            sliver: SliverList.list(
              children: [
                Text(
                  lodging.tipoHospedaje.toUpperCase(),
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.accentDark,
                    letterSpacing: 0.5,
                  ),
                ),
                const SizedBox(height: 4),
                Text(lodging.nombre, style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                      color: AppTheme.titleColor,
                    )),
                if (lodging.estrellas != null) ...[
                  const SizedBox(height: 6),
                  StarRow(count: lodging.estrellas!, size: 18),
                ],
                const SizedBox(height: 8),
                InfoLine(icon: Icons.place_outlined, text: location),
                if (lodging.direccion != null)
                  InfoLine(icon: Icons.signpost_outlined, text: lodging.direccion!),
                InfoLine(icon: Icons.business_outlined, text: 'Operado por ${lodging.empresa}'),
                if (schedule.isNotEmpty) InfoLine(icon: Icons.schedule, text: schedule),
                if (lodging.descripcion != null) ...[
                  const SizedBox(height: 16),
                  Text(lodging.descripcion!, style: const TextStyle(height: 1.5, color: AppTheme.labelColor)),
                ],
                if (lodging.servicios.isNotEmpty) ...[
                  const SizedBox(height: 20),
                  const _SectionTitle('Servicios'),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      for (final service in lodging.servicios)
                        Chip(
                          label: Text(service),
                          visualDensity: VisualDensity.compact,
                          side: const BorderSide(color: AppTheme.inputBorder),
                          backgroundColor: Colors.white,
                        ),
                    ],
                  ),
                ],
                if (lodging.precioDesde != null) ...[
                  const SizedBox(height: 20),
                  PriceBox(
                    label: 'Habitaciones desde',
                    price: formatPrice(lodging.monedaSimbolo, lodging.precioDesde)!,
                    note: 'por habitación/noche',
                  ),
                ],
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  onPressed: () => addProductToItinerary(
                    context,
                    productId: lodging.productoId,
                    productName: lodging.nombre,
                  ),
                  icon: const Icon(Icons.playlist_add),
                  label: const Text('Agregar a mi itinerario'),
                ),
                if (lodging.tieneUbicacion) ...[
                  const SizedBox(height: 20),
                  const _SectionTitle('Ubicación'),
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    onPressed: () => _openMap(lodging),
                    icon: const Icon(Icons.map_outlined),
                    label: const Text('Ver en el mapa'),
                  ),
                  const SizedBox(height: 4),
                  Text('Ubicación declarada por ${lodging.empresa}.', style: const TextStyle(fontSize: 12)),
                ],
                const SizedBox(height: 24),
                _SectionTitle(
                  _rooms.isEmpty
                      ? 'Tipos de habitación'
                      : 'Tipos de habitación (${_rooms.length})',
                ),
                const SizedBox(height: 8),
              ],
            ),
          ),
          if (_roomsError != null)
            SliverToBoxAdapter(child: ErrorRetry(message: _roomsError!, onRetry: _load))
          else if (_rooms.isEmpty)
            const SliverToBoxAdapter(
              child: EmptyState(
                icon: Icons.bed_outlined,
                title: 'Todavía no hay habitaciones publicadas',
                message: 'Vuelve más adelante o explora otros hospedajes.',
              ),
            )
          else
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 32),
              sliver: SliverList.separated(
                itemCount: _rooms.length,
                separatorBuilder: (_, _) => const SizedBox(height: 12),
                itemBuilder: (context, index) => _RoomTile(
                  room: _rooms[index],
                  onTap: () => _showRoom(_rooms[index]),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);

  final String text;

  @override
  Widget build(BuildContext context) => Text(text, style: Theme.of(context).textTheme.titleLarge);
}

String _guests(int count) => '$count ${count == 1 ? 'huésped' : 'huéspedes'}';

class _RoomTile extends StatelessWidget {
  const _RoomTile({required this.room, required this.onTap});

  final Room room;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final price = formatPrice(room.monedaSimbolo, room.precioNoche);
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
              width: 110,
              height: 120,
              child: ProductImage(url: room.imagenUrl, icon: Icons.bed_outlined),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      room.nombre,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.w700, color: AppTheme.titleColor),
                    ),
                    const SizedBox(height: 4),
                    Text('Hasta ${_guests(room.capacidadMaxima)}', style: const TextStyle(fontSize: 13)),
                    if (room.incluyeDesayuno)
                      const Text(
                        'Desayuno incluido',
                        style: TextStyle(fontSize: 13, color: Color(0xFF047857)),
                      ),
                    const SizedBox(height: 6),
                    if (price != null)
                      Text.rich(
                        TextSpan(
                          children: [
                            TextSpan(
                              text: price,
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w800,
                                color: AppTheme.accentDark,
                              ),
                            ),
                            const TextSpan(text: ' / noche', style: TextStyle(fontSize: 12)),
                          ],
                        ),
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

class _RoomSheet extends StatelessWidget {
  const _RoomSheet({required this.room, required this.onBook});

  final Room room;
  final VoidCallback onBook;

  @override
  Widget build(BuildContext context) {
    final price = formatPrice(room.monedaSimbolo, room.precioNoche);
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.75,
      maxChildSize: 0.95,
      builder: (context, controller) => ListView(
        controller: controller,
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: AspectRatio(
              aspectRatio: 16 / 9,
              child: ProductImage(url: room.imagenUrl, icon: Icons.bed_outlined),
            ),
          ),
          const SizedBox(height: 16),
          Text(room.nombre, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          InfoLine(
            icon: Icons.bed_outlined,
            text: '${room.cantidad} ${room.cantidad == 1 ? 'habitación' : 'habitaciones'} de este tipo',
          ),
          InfoLine(icon: Icons.people_outline, text: 'Hasta ${_guests(room.capacidadMaxima)} por habitación'),
          InfoLine(
            icon: Icons.person_outline,
            text: 'Máx. ${room.capacidadAdultos} ${room.capacidadAdultos == 1 ? 'adulto' : 'adultos'}'
                ' · Máx. ${room.capacidadNinos} ${room.capacidadNinos == 1 ? 'niño' : 'niños'}',
          ),
          if (room.tipoCama != null) InfoLine(icon: Icons.king_bed_outlined, text: room.tipoCama!),
          InfoLine(
            icon: Icons.free_breakfast_outlined,
            text: room.incluyeDesayuno ? 'Desayuno incluido' : 'Sin desayuno',
          ),
          if (room.descripcion != null) ...[
            const SizedBox(height: 16),
            Text(room.descripcion!, style: const TextStyle(height: 1.5, color: AppTheme.labelColor)),
          ],
          if (price != null) ...[
            const SizedBox(height: 20),
            PriceBox(label: 'Precio', price: price, note: 'por habitación/noche'),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: onBook,
              icon: const Icon(Icons.event_available),
              label: const Text('Reservar esta habitación'),
            ),
          ],
        ],
      ),
    );
  }
}
