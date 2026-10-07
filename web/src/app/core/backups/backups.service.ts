import { HttpClient, HttpResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export type BackupFrequency = 'DESACTIVADA' | 'CADA_3_DIAS' | 'SEMANAL';

export interface BackupSchedule {
  frecuencia: BackupFrequency;
  ultima_ejecucion: string | null;
  proxima_ejecucion: string | null;
  /** Sin almacén (Cloudinary) las copias automáticas no se pueden guardar. */
  almacen_configurado: boolean;
}

/** Copia guardada fuera del servidor por la programación o a pedido. */
export interface StoredBackup {
  id: number;
  archivo: string;
  tamano_bytes: number;
  sha256: string;
  origen: 'PROGRAMADA' | 'A_PEDIDO';
  creado_en: string;
  correos_enviados?: number;
}

@Injectable({ providedIn: 'root' })
export class BackupsService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/admin/copias-seguridad`;

  download(): Observable<HttpResponse<Blob>> {
    return this.http.post(`${this.baseUrl}/descargar/`, null, {
      observe: 'response',
      responseType: 'blob',
    });
  }

  schedule(): Observable<BackupSchedule> {
    return this.http.get<BackupSchedule>(`${this.baseUrl}/programacion/`);
  }

  updateSchedule(frecuencia: BackupFrequency): Observable<BackupSchedule> {
    return this.http.put<BackupSchedule>(`${this.baseUrl}/programacion/`, { frecuencia });
  }

  stored(): Observable<StoredBackup[]> {
    return this.http.get<StoredBackup[]>(`${this.baseUrl}/guardadas/`);
  }

  /** Genera una copia ahora, la guarda y avisa por correo al SuperAdmin. */
  createStored(): Observable<StoredBackup> {
    return this.http.post<StoredBackup>(`${this.baseUrl}/guardadas/`, null);
  }

  /** Enlace firmado de descarga; vence en pocos minutos. */
  link(id: number): Observable<{ url: string }> {
    return this.http.post<{ url: string }>(`${this.baseUrl}/guardadas/${id}/enlace/`, null);
  }
}
