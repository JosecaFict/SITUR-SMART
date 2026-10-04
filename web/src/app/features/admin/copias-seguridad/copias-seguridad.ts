import { HttpErrorResponse, HttpResponse } from '@angular/common/http';
import { Component, signal } from '@angular/core';
import {
  LucideCheckCircle2,
  LucideDatabaseBackup,
  LucideDownload,
  LucideFileArchive,
  LucideInfo,
  LucideShieldCheck,
} from '@lucide/angular';
import { BackupsService } from '../../../core/backups/backups.service';
import { apiErrorMessage } from '../../../core/http/api-error';

interface GeneratedBackup {
  filename: string;
  size: number;
  sha256: string;
}

@Component({
  selector: 'situr-copias-seguridad',
  imports: [
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
export class CopiasSeguridad {
  protected readonly generating = signal(false);
  protected readonly confirmationOpen = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly lastBackup = signal<GeneratedBackup | null>(null);

  constructor(private readonly backups: BackupsService) {}

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
        this.errorMessage.set(
          apiErrorMessage(error, 'No fue posible generar la copia de seguridad.'),
        );
      },
    });
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
