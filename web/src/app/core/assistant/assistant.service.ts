import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  AssistantChatResponse,
  AssistantHistoryItem,
  AssistantLodgingCard,
  AssistantStatus,
} from './assistant.models';

/**
 * Asistente virtual IA (CU36). El navegador nunca habla con el proveedor de IA:
 * la clave vive solo en el backend, que es quien llama a Groq / Gemini / Grok.
 */
@Injectable({ providedIn: 'root' })
export class AssistantService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/asistente`;

  status(): Observable<AssistantStatus> {
    return this.http.get<AssistantStatus>(`${this.baseUrl}/estado/`);
  }

  chat(mensaje: string, historial: AssistantHistoryItem[]): Observable<AssistantChatResponse> {
    return this.http.post<AssistantChatResponse>(`${this.baseUrl}/chat/`, { mensaje, historial });
  }

  transcribe(audio: Blob, filename: string): Observable<{ texto: string }> {
    const form = new FormData();
    form.append('audio', audio, filename);
    return this.http.post<{ texto: string }>(`${this.baseUrl}/voz/`, form);
  }

  recommendations(filters: Record<string, string | number>): Observable<AssistantLodgingCard[]> {
    return this.http.get<AssistantLodgingCard[]>(`${this.baseUrl}/recomendaciones/`, {
      params: filters,
    });
  }
}
