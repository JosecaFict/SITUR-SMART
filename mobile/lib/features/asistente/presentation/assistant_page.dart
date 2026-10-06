import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../marketplace/models/marketplace_models.dart';
import '../../marketplace/presentation/widgets/marketplace_widgets.dart';
import '../data/assistant_service.dart';

const _welcome =
    '¡Hola! Soy Situr, tu asistente de viaje. Puedo recomendarte hospedajes según tu ciudad, '
    'presupuesto y cantidad de personas. Escríbeme o usa el micrófono.';

const _suggestions = [
  'Hotel en Uyuni para 2 personas',
  '¿Qué ciudades tienen hospedajes?',
  'Algo económico con desayuno',
];

/// Una nota de voz más larga gasta cuota sin mejorar el pedido.
const _maxRecording = Duration(seconds: 30);

class _Message {
  const _Message({required this.rol, required this.texto, this.hospedajes = const [], this.error = false});

  final String rol;
  final String texto;
  final List<AssistantLodging> hospedajes;

  /// Los errores se muestran pero no viajan en el historial.
  final bool error;

  bool get esUsuario => rol == 'usuario';
}

/// Chat con el asistente IA (CU36). La voz se graba en el teléfono, el backend
/// la transcribe y el texto queda en la caja para revisarlo antes de enviarlo.
class AssistantPage extends StatefulWidget {
  const AssistantPage({super.key});

  @override
  State<AssistantPage> createState() => _AssistantPageState();
}

class _AssistantPageState extends State<AssistantPage> {
  final AssistantService _service = AssistantService();
  final TextEditingController _input = TextEditingController();
  final ScrollController _scroll = ScrollController();
  final AudioRecorder _recorder = AudioRecorder();

  final List<_Message> _messages = [const _Message(rol: 'asistente', texto: _welcome)];
  AssistantStatus? _status;
  bool _statusError = false;
  bool _sending = false;
  bool _recording = false;
  bool _transcribing = false;
  Timer? _recordingLimit;

  @override
  void initState() {
    super.initState();
    _loadStatus();
  }

  @override
  void dispose() {
    _recordingLimit?.cancel();
    _recorder.dispose();
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _loadStatus() async {
    setState(() => _statusError = false);
    try {
      final status = await _service.status();
      if (mounted) setState(() => _status = status);
    } catch (_) {
      if (mounted) setState(() => _statusError = true);
    }
  }

  bool get _busy => _sending || _transcribing;

  Future<void> _send([String? text]) async {
    final message = (text ?? _input.text).trim();
    if (message.isEmpty || _busy) return;

    final history = [
      for (final m in _messages.skip(1)) // el saludo no aporta contexto
        if (!m.error) ChatTurn(rol: m.rol, contenido: m.texto),
    ];
    _input.clear();
    setState(() {
      _messages.add(_Message(rol: 'usuario', texto: message));
      _sending = true;
    });
    _scrollToEnd();

    try {
      final reply = await _service.chat(message, history);
      if (!mounted) return;
      setState(() {
        _messages.add(_Message(rol: 'asistente', texto: reply.texto, hospedajes: reply.hospedajes));
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _messages.add(_Message(rol: 'asistente', texto: _errorText(error), error: true));
      });
    } finally {
      if (mounted) setState(() => _sending = false);
      _scrollToEnd();
    }
  }

  String _errorText(Object error) =>
      error is ApiException ? error.message : 'No se pudo conectar con el asistente. Revisa tu conexión.';

  void _clear() {
    setState(() {
      _messages
        ..clear()
        ..add(const _Message(rol: 'asistente', texto: _welcome));
    });
  }

  Future<void> _toggleRecording() async {
    if (_recording) {
      await _stopRecording();
      return;
    }
    if (_busy) return;
    if (!await _recorder.hasPermission()) {
      _snack('Necesitamos permiso para usar el micrófono.');
      return;
    }
    final dir = await getTemporaryDirectory();
    final path = '${dir.path}/nota_${DateTime.now().millisecondsSinceEpoch}.m4a';
    await _recorder.start(const RecordConfig(encoder: AudioEncoder.aacLc), path: path);
    _recordingLimit = Timer(_maxRecording, _stopRecording);
    if (mounted) setState(() => _recording = true);
  }

  Future<void> _stopRecording() async {
    _recordingLimit?.cancel();
    _recordingLimit = null;
    if (!_recording) return;
    final path = await _recorder.stop();
    if (!mounted) return;
    setState(() {
      _recording = false;
      _transcribing = path != null;
    });
    if (path == null) return;
    try {
      final text = await _service.transcribe(path);
      if (!mounted) return;
      if (text.isEmpty) {
        _snack('No se entendió el audio. Intenta de nuevo, hablando cerca del teléfono.');
      } else {
        // Se deja en la caja para que el turista lo corrija si hace falta.
        _input.text = text;
        _input.selection = TextSelection.collapsed(offset: text.length);
      }
    } catch (error) {
      if (mounted) _snack(_errorText(error));
    } finally {
      if (mounted) setState(() => _transcribing = false);
      try {
        await File(path).delete();
      } catch (_) {}
    }
  }

  void _snack(String text) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppTheme.accentDark,
        foregroundColor: Colors.white,
        title: const Text('Asistente Situr', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          if (_status?.chat == true && _messages.length > 1)
            IconButton(
              tooltip: 'Nueva conversación',
              onPressed: _busy ? null : _clear,
              icon: const Icon(Icons.refresh),
            ),
        ],
      ),
      body: _body(),
    );
  }

  Widget _body() {
    if (_statusError) {
      return ErrorRetry(message: 'No se pudo conectar con el asistente.', onRetry: _loadStatus);
    }
    final status = _status;
    if (status == null) return const Center(child: CircularProgressIndicator());
    if (!status.chat) {
      return const EmptyState(
        icon: Icons.smart_toy_outlined,
        title: 'El asistente no está disponible',
        message: 'Mientras tanto puedes buscar hospedajes en Explorar.',
      );
    }

    return Column(
      children: [
        Expanded(
          child: ListView.builder(
            controller: _scroll,
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            itemCount: _messages.length + (_sending ? 1 : 0),
            itemBuilder: (context, index) {
              if (index == _messages.length) return const _TypingBubble();
              return _Bubble(message: _messages[index]);
            },
          ),
        ),
        if (_messages.length == 1)
          SizedBox(
            height: 48,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: _suggestions.length,
              separatorBuilder: (_, _) => const SizedBox(width: 8),
              itemBuilder: (context, index) => ActionChip(
                label: Text(_suggestions[index]),
                onPressed: () => _send(_suggestions[index]),
              ),
            ),
          ),
        _composer(status),
      ],
    );
  }

  Widget _composer(AssistantStatus status) {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
        child: Row(
          children: [
            if (status.voz)
              IconButton.filledTonal(
                tooltip: _recording ? 'Detener grabación' : 'Hablar',
                onPressed: (_busy && !_recording) ? null : _toggleRecording,
                style: _recording
                    ? IconButton.styleFrom(backgroundColor: AppTheme.errorColor, foregroundColor: Colors.white)
                    : null,
                icon: _transcribing
                    ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : Icon(_recording ? Icons.stop : Icons.mic_none),
              ),
            const SizedBox(width: 6),
            Expanded(
              child: TextField(
                controller: _input,
                enabled: !_recording,
                minLines: 1,
                maxLines: 4,
                maxLength: 1000,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _send(),
                decoration: InputDecoration(
                  counterText: '',
                  hintText: _recording
                      ? 'Escuchando… toca detener al terminar'
                      : _transcribing
                          ? 'Transcribiendo…'
                          : 'Escribe tu consulta',
                ),
              ),
            ),
            const SizedBox(width: 6),
            IconButton.filled(
              tooltip: 'Enviar',
              onPressed: _busy || _recording ? null : _send,
              icon: const Icon(Icons.send),
            ),
          ],
        ),
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.message});

  final _Message message;

  @override
  Widget build(BuildContext context) {
    final mine = message.esUsuario;
    final background = mine
        ? AppTheme.accentDark
        : message.error
            ? const Color(0xFFFEF2F2)
            : AppTheme.inputBg;
    final foreground = mine
        ? Colors.white
        : message.error
            ? const Color(0xFFB91C1C)
            : AppTheme.titleColor;

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: mine ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          ConstrainedBox(
            constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.8),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: background,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16),
                  topRight: const Radius.circular(16),
                  bottomLeft: Radius.circular(mine ? 16 : 4),
                  bottomRight: Radius.circular(mine ? 4 : 16),
                ),
                border: mine ? null : Border.all(color: AppTheme.inputBorder),
              ),
              child: SelectableText(message.texto, style: TextStyle(color: foreground, height: 1.4)),
            ),
          ),
          if (message.hospedajes.isNotEmpty) ...[
            const SizedBox(height: 8),
            SizedBox(
              height: 210,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: message.hospedajes.length,
                separatorBuilder: (_, _) => const SizedBox(width: 10),
                itemBuilder: (context, index) => _LodgingSuggestion(lodging: message.hospedajes[index]),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _LodgingSuggestion extends StatelessWidget {
  const _LodgingSuggestion({required this.lodging});

  final AssistantLodging lodging;

  @override
  Widget build(BuildContext context) {
    final price = formatPrice(lodging.moneda, lodging.precioDesde);
    return SizedBox(
      width: 200,
      child: Card(
        margin: EdgeInsets.zero,
        elevation: 0,
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: const BorderSide(color: AppTheme.inputBorder),
        ),
        child: InkWell(
          onTap: () => context.push('/hospedaje/${lodging.id}'),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                height: 100,
                width: double.infinity,
                child: ProductImage(url: lodging.imagenUrl, icon: Icons.hotel_outlined),
              ),
              Padding(
                padding: const EdgeInsets.all(10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      lodging.nombre,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.w700, color: AppTheme.titleColor),
                    ),
                    if (lodging.estrellas != null) StarRow(count: lodging.estrellas!, size: 13),
                    Text(
                      lodging.localidad == null ? lodging.ciudad : '${lodging.localidad}, ${lodging.ciudad}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 12),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      price == null ? 'Ver habitaciones →' : 'Desde $price',
                      style: const TextStyle(fontWeight: FontWeight.w800, color: AppTheme.accentDark),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TypingBubble extends StatelessWidget {
  const _TypingBubble();

  @override
  Widget build(BuildContext context) {
    return const Align(
      alignment: Alignment.centerLeft,
      child: Padding(
        padding: EdgeInsets.only(bottom: 10),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
            SizedBox(width: 10),
            Text('Situr está escribiendo…'),
          ],
        ),
      ),
    );
  }
}
