import { HttpErrorResponse } from '@angular/common/http';
import {
  Component,
  ElementRef,
  OnDestroy,
  computed,
  effect,
  inject,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  LucideBot,
  LucideFileSpreadsheet,
  LucideFileText,
  LucideLoaderCircle,
  LucideMapPin,
  LucideMic,
  LucideSend,
  LucideSparkles,
  LucideSquare,
  LucideStar,
  LucideTrash2,
  LucideVolume2,
  LucideVolumeX,
  LucideX,
} from '@lucide/angular';
import { AssistantLodgingCard, AssistantReport } from '../../core/assistant/assistant.models';
import { AssistantService } from '../../core/assistant/assistant.service';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error';
import { ReportsService } from '../../core/reports/reports.service';

interface ChatMessage {
  rol: 'usuario' | 'asistente';
  contenido: string;
  hospedajes?: AssistantLodgingCard[];
  reportes?: AssistantReport[];
  error?: boolean;
}

const WELCOME =
  '¡Hola! Soy Situr, tu asistente de viaje. Puedo recomendarte hospedajes según tu ciudad, ' +
  'presupuesto y cantidad de personas. Escríbeme o usa el micrófono 🎤.';

const SUGGESTIONS = [
  'Hotel en Uyuni para 2 personas',
  '¿Qué ciudades tienen hospedajes?',
  'Algo económico con desayuno',
];

const STAFF_WELCOME =
  '¡Hola! Soy Situr. Además de recomendar hospedajes, te preparo reportes: pídemelos ' +
  'escribiendo o por voz 🎤, por ejemplo "el catálogo de este mes en PDF".';

const STAFF_SUGGESTIONS = [
  'Reporte del catálogo en PDF',
  'Actividad de este mes en Excel',
  '¿Cuántos hospedajes tengo?',
];

/** Cuántos mensajes previos viajan al backend; el backend recorta igual a 10. */
const HISTORY_LIMIT = 10;
/** Una nota de voz más larga gasta cuota sin mejorar el pedido. */
const MAX_RECORDING_MS = 30_000;

/**
 * Chat flotante del asistente virtual IA (CU36).
 *
 * Solo aparece con sesión iniciada y si el backend tiene proveedor de IA
 * configurado (/asistente/estado/). Sin clave, no se muestra nada.
 *
 * La voz se graba en el navegador con MediaRecorder y se transcribe en el
 * backend (Whisper), así funciona igual en Chrome, Edge, Firefox y Safari. La
 * lectura en voz alta usa speechSynthesis del navegador: es gratis y no pasa
 * por el servidor.
 */
@Component({
  selector: 'situr-asistente-chat',
  imports: [
    FormsModule, RouterLink, LucideBot, LucideFileSpreadsheet, LucideFileText, LucideLoaderCircle, LucideMapPin, LucideMic,
    LucideSend, LucideSparkles, LucideSquare, LucideStar, LucideTrash2, LucideVolume2,
    LucideVolumeX, LucideX,
  ],
  templateUrl: './asistente-chat.html',
})
export class AsistenteChat implements OnDestroy {
  private readonly assistant = inject(AssistantService);
  private readonly auth = inject(AuthService);
  private readonly reports = inject(ReportsService);
  private readonly scroller = viewChild<ElementRef<HTMLElement>>('scroller');

  /**
   * Empresa en nombre de la que habla el personal; null para el SuperAdmin
   * (reportes de toda la plataforma) y para el turista.
   */
  private readonly tenantId = computed(() => {
    const user = this.auth.session?.()?.user;
    return user && !user.roles.includes('SUPER_ADMIN') ? (user.tenants[0]?.id ?? null) : null;
  });
  /** Quien puede pedir reportes: SuperAdmin o personal de una empresa. */
  protected readonly staff = computed(() => {
    const user = this.auth.session?.()?.user;
    return !!user && (user.roles.includes('SUPER_ADMIN') || user.tenants.length > 0);
  });
  protected readonly suggestions = computed(() => (this.staff() ? STAFF_SUGGESTIONS : SUGGESTIONS));
  protected readonly downloading = signal<string | null>(null);
  protected readonly enabled = signal(false);
  protected readonly voiceEnabled = signal(false);
  protected readonly open = signal(false);
  protected readonly sending = signal(false);
  protected readonly recording = signal(false);
  protected readonly transcribing = signal(false);
  protected readonly speak = signal(false);
  protected readonly messages = signal<ChatMessage[]>([{ rol: 'asistente', contenido: this.welcome() }]);
  protected draft = '';

  protected readonly visible = computed(() => this.enabled() && this.auth.isAuthenticated());
  protected readonly busy = computed(() => this.sending() || this.transcribing());
  protected readonly canRecord =
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== 'undefined';
  protected readonly canSpeak = typeof window !== 'undefined' && 'speechSynthesis' in window;

  private recorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private chunks: Blob[] = [];
  private stopTimer: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    this.assistant.status().subscribe({
      next: (status) => {
        this.enabled.set(status.chat);
        this.voiceEnabled.set(status.voz);
      },
      // Backend sin el endpoint o caído: simplemente no se muestra el chat.
      error: () => this.enabled.set(false),
    });

    // El chat vive en la raíz y se crea antes del login: al iniciar sesión el
    // personal tiene que ver su saludo (con reportes) si todavía no conversó.
    effect(() => {
      const contenido = this.welcome();
      if (untracked(this.messages).length === 1) this.messages.set([{ rol: 'asistente', contenido }]);
    });

    // Baja al último mensaje cada vez que cambia la conversación.
    effect(() => {
      this.messages();
      this.busy();
      queueMicrotask(() => {
        const el = this.scroller()?.nativeElement;
        if (el) el.scrollTop = el.scrollHeight;
      });
    });
  }

  ngOnDestroy(): void {
    this.releaseMicrophone();
    if (this.canSpeak) window.speechSynthesis.cancel();
  }

  protected toggle(): void {
    this.open.update((value) => !value);
    if (!this.open()) this.stopSpeaking();
  }

  protected toggleSpeak(): void {
    this.speak.update((value) => !value);
    if (!this.speak()) this.stopSpeaking();
  }

  protected clear(): void {
    this.stopSpeaking();
    this.messages.set([{ rol: 'asistente', contenido: this.welcome() }]);
  }

  protected send(text = this.draft): void {
    const mensaje = text.trim();
    if (!mensaje || this.busy()) return;

    const historial = this.messages()
      .slice(1) // el saludo no aporta contexto
      .filter((m) => !m.error)
      .slice(-HISTORY_LIMIT)
      .map(({ rol, contenido }) => ({ rol, contenido }));

    this.draft = '';
    this.messages.update((list) => [...list, { rol: 'usuario', contenido: mensaje }]);
    this.sending.set(true);

    this.assistant.chat(mensaje, historial, this.tenantId()).subscribe({
      next: (response) => {
        const contenido = this.plain(response.respuesta);
        const reportes = response.reportes ?? [];
        this.messages.update((list) => [
          ...list,
          { rol: 'asistente', contenido, hospedajes: response.hospedajes, reportes },
        ]);
        this.sending.set(false);
        this.say(contenido);
        // Pidió el archivo ("en PDF", "en Excel"): se baja sin otro clic.
        for (const report of reportes) {
          if (report.formato) this.downloadReport(report, report.formato);
        }
      },
      error: (error: HttpErrorResponse) => {
        this.messages.update((list) => [
          ...list,
          { rol: 'asistente', contenido: apiErrorMessage(error), error: true },
        ]);
        this.sending.set(false);
      },
    });
  }

  protected onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  // --- Reportes ---------------------------------------------------------------

  protected downloadReport(report: AssistantReport, format: 'pdf' | 'excel'): void {
    const key = `${report.tipo}-${format}`;
    if (this.downloading()) return;
    this.downloading.set(key);
    const filters = {
      tipo: report.tipo,
      ...(report.desde ? { desde: report.desde } : {}),
      ...(report.hasta ? { hasta: report.hasta } : {}),
    };
    const extension = format === 'excel' ? 'xlsx' : 'pdf';
    this.reports.export(report.empresa_id, filters, extension).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `reporte-${report.tipo}.${extension}`;
        link.click();
        URL.revokeObjectURL(url);
        this.downloading.set(null);
      },
      error: (error: HttpErrorResponse) => {
        this.downloading.set(null);
        this.pushError(apiErrorMessage(error, 'No se pudo descargar el reporte.'));
      },
    });
  }

  protected reportPeriod(report: AssistantReport): string {
    const day = (value: string) => value.split('-').reverse().join('/');
    if (report.desde && report.hasta) return `${day(report.desde)} al ${day(report.hasta)}`;
    if (report.desde) return `desde ${day(report.desde)}`;
    if (report.hasta) return `hasta ${day(report.hasta)}`;
    return 'todas las fechas';
  }

  private welcome(): string {
    return this.staff() ? STAFF_WELCOME : WELCOME;
  }

  // --- Voz -------------------------------------------------------------------

  protected async toggleRecording(): Promise<void> {
    if (this.recording()) {
      this.recorder?.stop();
      return;
    }
    if (this.busy()) return;
    this.stopSpeaking();

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      this.pushError('No se pudo usar el micrófono. Revisa el permiso del navegador.');
      return;
    }

    // Chrome, Edge y Firefox graban webm/opus; Safari solo mp4.
    const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find((type) =>
      MediaRecorder.isTypeSupported(type),
    );
    this.recorder = new MediaRecorder(this.stream, mimeType ? { mimeType } : undefined);
    this.chunks = [];
    this.recorder.ondataavailable = (event) => {
      if (event.data.size > 0) this.chunks.push(event.data);
    };
    this.recorder.onstop = () => this.onRecordingStopped();
    this.recorder.start();
    this.recording.set(true);
    this.stopTimer = setTimeout(() => this.recorder?.stop(), MAX_RECORDING_MS);
  }

  private onRecordingStopped(): void {
    const type = this.recorder?.mimeType || 'audio/webm';
    this.recording.set(false);
    this.releaseMicrophone();

    const audio = new Blob(this.chunks, { type });
    this.chunks = [];
    if (audio.size === 0) return;

    const extension = type.includes('mp4') ? 'm4a' : 'webm';
    this.transcribing.set(true);
    this.assistant.transcribe(audio, `voz.${extension}`).subscribe({
      next: ({ texto }) => {
        this.transcribing.set(false);
        if (!texto) {
          this.pushError('No te entendí bien. ¿Puedes repetirlo?');
          return;
        }
        // Quien habla espera que le respondan hablando.
        if (this.canSpeak) this.speak.set(true);
        this.send(texto);
      },
      error: (error: HttpErrorResponse) => {
        this.transcribing.set(false);
        this.pushError(apiErrorMessage(error));
      },
    });
  }

  private releaseMicrophone(): void {
    if (this.stopTimer) clearTimeout(this.stopTimer);
    this.stopTimer = null;
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
  }

  private say(text: string): void {
    if (!this.speak() || !this.canSpeak) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text.replace(/[\p{Extended_Pictographic}]/gu, ''));
    utterance.lang = 'es-ES';
    const spanish = window.speechSynthesis.getVoices().find((voice) => voice.lang.startsWith('es'));
    if (spanish) utterance.voice = spanish;
    window.speechSynthesis.speak(utterance);
  }

  private stopSpeaking(): void {
    if (this.canSpeak) window.speechSynthesis.cancel();
  }

  private pushError(contenido: string): void {
    this.messages.update((list) => [...list, { rol: 'asistente', contenido, error: true }]);
  }

  /** El modelo a veces responde con Markdown; el chat lo muestra como texto. */
  private plain(text: string): string {
    return text
      .replace(/\*\*(.+?)\*\*/g, '$1')
      .replace(/^#{1,6}\s+/gm, '')
      .replace(/^\s*[*-]\s+/gm, '• ')
      .trim();
  }
}
