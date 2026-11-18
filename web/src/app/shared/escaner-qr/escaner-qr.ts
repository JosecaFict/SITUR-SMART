import { Component, ElementRef, OnDestroy, OnInit, output, signal, viewChild } from '@angular/core';
import { LucideX } from '@lucide/angular';
import jsQR from 'jsqr';

/**
 * Abre la cámara y lee un código QR. Cuando lo encuentra emite su contenido
 * en (leido) y apaga la cámara. (cerrar) avisa que el usuario canceló.
 */
@Component({
  selector: 'situr-escaner-qr',
  imports: [LucideX],
  template: `
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-label="Escanear código QR">
      <div class="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl">
        <div class="flex items-center justify-between">
          <h2 class="text-title font-bold">Escanear voucher</h2>
          <button type="button" class="icon-button" (click)="close()" aria-label="Cerrar">
            <svg lucideX class="h-5 w-5"></svg>
          </button>
        </div>

        @if (error(); as message) {
          <p class="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{{ message }}</p>
        } @else {
          <p class="text-text-secondary mt-1 text-sm">Apunta la cámara al QR del cliente.</p>
          <div class="relative mt-4 overflow-hidden rounded-xl bg-black">
            <video #video class="aspect-square w-full object-cover" playsinline muted></video>
            <div class="pointer-events-none absolute inset-10 rounded-xl border-4 border-white/80"></div>
            @if (starting()) {
              <p class="absolute inset-0 flex items-center justify-center text-sm text-white">Encendiendo la cámara…</p>
            }
          </div>
        }

        <canvas #canvas class="hidden"></canvas>
        <button type="button" class="secondary-button mt-4 w-full" (click)="close()">Cancelar</button>
      </div>
    </div>
  `,
})
export class EscanerQr implements OnInit, OnDestroy {
  readonly leido = output<string>();
  readonly cerrar = output<void>();

  private readonly video = viewChild<ElementRef<HTMLVideoElement>>('video');
  private readonly canvas = viewChild.required<ElementRef<HTMLCanvasElement>>('canvas');

  protected readonly starting = signal(true);
  protected readonly error = signal<string | null>(null);

  private stream: MediaStream | null = null;
  private frame = 0;

  async ngOnInit(): Promise<void> {
    if (!navigator.mediaDevices?.getUserMedia) {
      this.error.set('Este navegador no permite usar la cámara. Escribe el código a mano.');
      return;
    }
    try {
      // facingMode "environment" = cámara trasera en celulares; en PC usa la webcam.
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
        audio: false,
      });
      const video = this.video()?.nativeElement;
      if (!video) return;
      video.srcObject = this.stream;
      await video.play();
      this.starting.set(false);
      this.scan();
    } catch (err) {
      this.error.set(this.cameraError(err));
    }
  }

  ngOnDestroy(): void {
    this.stop();
  }

  protected close(): void {
    this.stop();
    this.cerrar.emit();
  }

  /** Copia cada cuadro del video al canvas y le pide a jsQR que busque un QR. */
  private scan(): void {
    const video = this.video()?.nativeElement;
    const canvas = this.canvas().nativeElement;
    const context = canvas.getContext('2d', { willReadFrequently: true });
    if (!video || !context) return;

    if (video.readyState === video.HAVE_ENOUGH_DATA) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      const image = context.getImageData(0, 0, canvas.width, canvas.height);
      const code = jsQR(image.data, image.width, image.height, { inversionAttempts: 'dontInvert' });
      if (code?.data) {
        this.stop();
        this.leido.emit(code.data);
        return;
      }
    }
    this.frame = requestAnimationFrame(() => this.scan());
  }

  private stop(): void {
    cancelAnimationFrame(this.frame);
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
  }

  private cameraError(err: unknown): string {
    const name = err instanceof DOMException ? err.name : '';
    if (name === 'NotAllowedError') return 'No diste permiso para usar la cámara. Actívalo en el candado de la barra de direcciones.';
    if (name === 'NotFoundError') return 'No se encontró ninguna cámara en este equipo.';
    if (name === 'NotReadableError') return 'La cámara está siendo usada por otra aplicación.';
    return 'No se pudo encender la cámara.';
  }
}