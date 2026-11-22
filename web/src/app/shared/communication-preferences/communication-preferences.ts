import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommunicationPreferences as Preferences } from '../../core/communications/communications.models';
import { CommunicationsService } from '../../core/communications/communications.service';
import { apiErrorMessage } from '../../core/http/api-error';

@Component({
  selector: 'situr-communication-preferences',
  template: `
    <section class="border-input-border rounded-2xl border bg-white p-5 space-y-3" aria-labelledby="preferences-title">
      <h2 id="preferences-title" class="text-title font-bold">Preferencias de promociones</h2>
      <p class="text-text-secondary text-sm">Elige de quién recibir ofertas. Desactivarlas no afecta los avisos de tus reservas ni las comunicaciones internas.</p>
      @if (loading()) { <p role="status">Cargando preferencias…</p> }
      @if (error(); as text) { <p role="alert" class="text-sm text-red-700">{{ text }}</p><button type="button" class="secondary-button" (click)="load()" [disabled]="saving()">Reintentar</button> }
      @if (preferences(); as result) {
        @for (item of result.preferencias; track item.empresa_id) {
          <label class="flex items-center justify-between gap-4 border-b border-input-border py-3 text-sm">
            <span>{{ item.nombre }}</span><input type="checkbox" [checked]="item.promociones" [disabled]="saving()" (change)="set(item.empresa_id, $event)" [attr.aria-label]="'Recibir promociones de ' + item.nombre">
          </label>
        }
        <p class="text-text-secondary text-xs">Máximo {{ result.limites.por_empresa_24h }} por remitente y {{ result.limites.total_24h }} promociones en total cada 24 horas.</p>
      }
      @if (success()) { <p role="status" class="text-sm text-teal-800">Preferencia guardada.</p> }
    </section>
  `,
})
export class CommunicationPreferences implements OnInit {
  private readonly service = inject(CommunicationsService);
  private readonly destroyRef = inject(DestroyRef);
  readonly preferences = signal<Preferences | null>(null);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly success = signal(false);

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true); this.error.set(null);
    this.service.preferences().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (result) => { this.preferences.set(result); this.loading.set(false); },
      error: (error: HttpErrorResponse) => { this.error.set(apiErrorMessage(error, 'No se pudieron cargar las preferencias.')); this.loading.set(false); },
    });
  }

  set(companyId: number | null, event: Event): void {
    const input = event.target as HTMLInputElement;
    const enabled = input.checked;
    input.checked = !enabled; // Show only the value confirmed by the server.
    if (this.saving()) return;
    this.saving.set(true); this.error.set(null); this.success.set(false);
    this.service.setPreference(companyId, enabled).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (result) => { this.preferences.set(result); this.saving.set(false); this.success.set(true); },
      error: (error: HttpErrorResponse) => { this.saving.set(false); this.error.set(apiErrorMessage(error, 'No se pudo guardar la preferencia.')); },
    });
  }
}
