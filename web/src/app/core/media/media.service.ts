import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { MediaUploadResponse } from './media.models';

@Injectable({ providedIn: 'root' })
export class MediaService {
  private readonly http = inject(HttpClient);

  /**
   * Sube una imagen a Cloudinary a través del backend de SITUR-SMART.
   * @param file Archivo File a subir.
   * @param folder Subcarpeta lógica en Cloudinary ('productos', 'empresas', etc.).
   */
  uploadImage(file: File, folder = 'productos'): Observable<MediaUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('folder', folder);

    return this.http.post<MediaUploadResponse>(`${environment.apiUrl}/media/upload/`, formData);
  }
}
