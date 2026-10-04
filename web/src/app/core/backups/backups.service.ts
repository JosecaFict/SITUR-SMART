import { HttpClient, HttpResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class BackupsService {
  private readonly http = inject(HttpClient);

  download(): Observable<HttpResponse<Blob>> {
    return this.http.post(`${environment.apiUrl}/admin/copias-seguridad/descargar/`, null, {
      observe: 'response',
      responseType: 'blob',
    });
  }
}
