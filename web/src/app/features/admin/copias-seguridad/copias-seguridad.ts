import { DatePipe } from '@angular/common';
import { HttpErrorResponse, HttpResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import {
  LucideCalendarClock,
  LucideCheckCircle2,
  LucideDatabaseBackup,
  LucideDownload,
  LucideFileArchive,
  LucideInfo,
  LucideShieldCheck,
} from '@lucide/angular';
import {
  BackupFrequency,
  BackupSchedule,
  BackupsService,
  StoredBackup,
} from '../../../core/backups/backups.service';
import { apiErrorMessage } from '../../../core/http/api-error';

const FREQUENCIES: { value: BackupFrequency; label: string }[] = [
  { value: 'DESACTIVADA', label: 'Desactivada' },
  { value: 'CADA_3_DIAS', label: 'Cada 3 días' },
  { value: 'SEMANAL', label: 'Semanal' },
];

interface GeneratedBackup {
  filename: string;
  size: number;
  sha256: string;
}

@Component({
  selector: 'situr-copias-seguridad',
  imports: [
    DatePipe,
    LucideCalendarClock,
    LucideCheckCircle2,
    LucideDatabaseBackup,
    LucideDownload,
    LucideFileArchive,
    LucideInfo,
    LucideShieldCheck,
  ],
  templateUrl: './copias-seguridad.html',
  styleUrl: './copias-seguridad.css',
})
export class CopiasSeguridad implements OnInit {
  private readonly route = inject(ActivatedRoute);

  protected readonly generating = signal(false);
  protected readonly confirmationOpen = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly lastBackup = signal<GeneratedBackup | null>(null);

  // Copia automática: cada cuánto se genera sola y las que quedaron guardadas.
  protected readonly frequencies = FREQUENCIES;
  protected readonly schedule = signal<BackupSchedule | null>(null);
  protected readonly stored = signal<StoredBackup[]>([]);
  protected readonly savingSchedule = signal(false);
  protected readonly creatingStored = signal(false);
  protected readonly downloadingId = signal<number | null>(null);
  protected readonly autoMessage = signal<string | null>(null);
  protected readonly autoError = signal<string | null>(null);

  constructor(private readonly backups: BackupsService) {}

  ngOnInit(): void {
    this.backups.schedule().subscribe({
      next: (schedule) => this.schedule.set(schedule),
      error: (error: HttpErrorResponse) =>
        this.autoError.set(apiErrorMessage(error, 'No se pudo cargar la programación.')),
    });
    // El correo de "copia lista" trae ?copia=ID: se baja apenas se abre la página.
    const requested = Number(this.route.snapshot.queryParamMap.get('copia'));
    this.loadStored(Number.isInteger(requested) && requested > 0 ? requested : null);
  }

  private loadStored(downloadId: number | null = null): void {
    this.backups.stored().subscribe({
      next: (list) => {
        this.stored.set(list);
        if (downloadId === null) return;
        if (list.some((backup) => backup.id === downloadId)) {
          this.downloadStored(downloadId);
        } else {
          this.autoError.set('Esa copia ya no está disponible: se conservan solo las últimas 8.');
        }
      },
      error: () => this.stored.set([]),
    });
  }

  protected changeFrequency(frecuencia: BackupFrequency): void {
    if (this.savingSchedule() || this.schedule()?.frecuencia === frecuencia) return;
    this.savingSchedule.set(true);
    this.autoMessage.set(null);
    this.autoError.set(null);
    this.backups.updateSchedule(frecuencia).subscribe({
      next: (schedule) => {
        this.schedule.set(schedule);
        this.savingSchedule.set(false);
        this.autoMessage.set(
          frecuencia === 'DESACTIVADA'
            ? 'La copia automática quedó desactivada.'
            : 'Programación guardada. Te avisaremos por correo cada vez que haya una copia nueva.',
        );
      },
      error: (error: HttpErrorResponse) => {
        this.savingSchedule.set(false);
        this.autoError.set(apiErrorMessage(error, 'No se pudo guardar la programación.'));
      },
    });
  }

  protected createStored(): void {
    if (this.creatingStored()) return;
    this.creatingStored.set(true);
    this.autoMessage.set(null);
    this.autoError.set(null);
    this.backups.createStored().subscribe({
      next: (backup) => {
        this.creatingStored.set(false);
        this.autoMessage.set(
          backup.correos_enviados
            ? 'Copia guardada. Te enviamos el enlace por correo.'
            : 'Copia guardada. No se pudo enviar el correo; descárgala desde la lista.',
        );
        this.loadStored();
      },
      error: (error: HttpErrorResponse) => {
        this.creatingStored.set(false);
        this.autoError.set(apiErrorMessage(error, 'No se pudo generar la copia.'));
      },
    });
  }

  protected downloadStored(id: number): void {
    if (this.downloadingId() !== null) return;
    this.downloadingId.set(id);
    this.backups.link(id).subscribe({
      next: ({ url }) => {
        this.downloadingId.set(null);
        // Enlace firmado de Cloudinary: el navegador baja el archivo directo.
        window.location.assign(url);
      },
      error: (error: HttpErrorResponse) => {
        this.downloadingId.set(null);
        this.autoError.set(apiErrorMessage(error, 'No se pudo preparar la descarga.'));
      },
    });
  }

  protected requestBackup(): void {
    this.confirmationOpen.set(true);
    this.errorMessage.set(null);
  }

  protected cancelBackup(): void {
    this.confirmationOpen.set(false);
  }

  protected generateBackup(): void {
    if (this.generating()) return;
    this.confirmationOpen.set(false);
    this.generating.set(true);
    this.errorMessage.set(null);
    this.backups.download().subscribe({
      next: (response) => this.saveResponse(response),
      error: (error: HttpErrorResponse) => {
        this.generating.set(false);
        this.showDownloadError(error);
      },
    });
  }

  private showDownloadError(error: HttpErrorResponse): void {
    if (error.error instanceof Blob) {
      error.error
        .text()
        .then((text) => {
          let body: unknown = text;
          try {
            body = JSON.parse(text);
          } catch {
            // Una respuesta HTML o texto plano se procesa con la misma utilidad común.
          }
          this.errorMessage.set(
            apiErrorMessage(
              new HttpErrorResponse({ error: body, status: error.status }),
              'No fue posible generar la copia de seguridad.',
            ),
          );
        })
        .catch(() =>
          this.errorMessage.set('No fue posible leer la respuesta del servidor.'),
        );
      return;
    }
    this.errorMessage.set(
      apiErrorMessage(error, 'No fue posible generar la copia de seguridad.'),
    );
  }

  private saveResponse(response: HttpResponse<Blob>): void {
    const blob = response.body;
    if (!blob) {
      this.generating.set(false);
      this.errorMessage.set('El servidor respondió sin un archivo de respaldo.');
      return;
    }
    const filename = this.filenameFrom(response) ?? 'situr-smart.dump';
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
    this.lastBackup.set({
      filename,
      size: blob.size,
      sha256: response.headers.get('X-Backup-SHA256') ?? '',
    });
    this.generating.set(false);
  }

  private filenameFrom(response: HttpResponse<Blob>): string | null {
    const disposition = response.headers.get('Content-Disposition') ?? '';
    const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
    if (encoded) return decodeURIComponent(encoded);
    return disposition.match(/filename="?([^";]+)"?/i)?.[1] ?? null;
  }

  protected formatBytes(bytes: number): string {
    if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
}
