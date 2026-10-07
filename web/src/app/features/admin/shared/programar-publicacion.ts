import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, input, output, signal } from '@angular/core';
import { Observable } from 'rxjs';
import { LucideCalendarClock } from '@lucide/angular';
import { apiErrorMessage } from '../../../core/http/api-error';
import { TourismProduct } from '../../../core/products/products.models';
import { ProductsService } from '../../../core/products/products.service';

/** "2026-10-15T08:00" en hora local del navegador, a partir de un ISO del backend. */
function toLocalInput(value: string | null | undefined): string {
  if (!value) return '';
  const date = new Date(value);
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/**
 * Publicar y/o retirar un producto o un hospedaje en una fecha y hora. El
 * sistema lo hace solo (revisa cada 10 minutos), lo deja en la bitácora y
 * avisa por correo.
 */
@Component({
  selector: 'situr-programar-publicacion',
  imports: [DatePipe, LucideCalendarClock],
  template: `
    <div class="rounded-xl border border-sky-200 bg-sky-50/60 p-4">
      <p class="flex items-center gap-2 text-sm font-semibold text-sky-900">
        <svg lucideCalendarClock class="h-4 w-4"></svg> Publicación programada
      </p>
      @if (publicarEn() || retirarEn()) {
        <p class="mt-1 text-xs text-sky-900">
          @if (publicarEn(); as when) { Se publica el {{ when | date: 'dd/MM/yyyy HH:mm' }}. }
          @if (retirarEn(); as when) { Se retira el {{ when | date: 'dd/MM/yyyy HH:mm' }}. }
        </p>
      }
      <div class="mt-3 grid gap-3 sm:grid-cols-2">
        @if (estado() !== 'PUBLICADO') {
          <label class="flex flex-col gap-1 text-xs font-semibold text-label">Publicar el
            <input type="datetime-local" class="field-control" [value]="publish()" (input)="publish.set($any($event.target).value)" aria-label="Publicar el" />
          </label>
        }
        <label class="flex flex-col gap-1 text-xs font-semibold text-label">Retirar el (opcional)
          <input type="datetime-local" class="field-control" [value]="withdraw()" (input)="withdraw.set($any($event.target).value)" aria-label="Retirar el" />
        </label>
      </div>
      <p class="mt-2 text-xs text-text-secondary">
        Se aplica sola dentro de los 10 minutos siguientes a la hora elegida y te avisamos por correo.
      </p>
      @if (error(); as text) { <p class="mt-2 text-xs font-semibold text-red-700">{{ text }}</p> }
      <div class="mt-3 flex flex-wrap gap-2">
        <button type="button" class="primary-button" [disabled]="working()" (click)="save()">Guardar programación</button>
        @if (publicarEn() || retirarEn()) {
          <button type="button" class="secondary-button" [disabled]="working()" (click)="clear()">Quitar programación</button>
        }
      </div>
    </div>
  `,
})
export class ProgramarPublicacion implements OnInit {
  private readonly products = inject(ProductsService);

  readonly tenantId = input.required<number>();
  readonly productId = input.required<number>();
  readonly estado = input.required<string>();
  readonly publicarEn = input<string | null | undefined>(null);
  readonly retirarEn = input<string | null | undefined>(null);
  readonly saved = output<TourismProduct>();

  protected readonly publish = signal('');
  protected readonly withdraw = signal('');
  protected readonly working = signal(false);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.publish.set(toLocalInput(this.publicarEn()));
    this.withdraw.set(toLocalInput(this.retirarEn()));
  }

  protected save(): void {
    const publish = this.estado() === 'PUBLICADO' ? '' : this.publish();
    if (!publish && !this.withdraw()) {
      this.error.set('Elige cuándo publicar o cuándo retirar.');
      return;
    }
    this.run(
      this.products.schedule(this.tenantId(), this.productId(), {
        // datetime-local es hora local: new Date() la interpreta con la zona del navegador.
        publicar_en: publish ? new Date(publish).toISOString() : null,
        retirar_en: this.withdraw() ? new Date(this.withdraw()).toISOString() : null,
      }),
    );
  }

  protected clear(): void {
    this.publish.set('');
    this.withdraw.set('');
    this.run(this.products.clearSchedule(this.tenantId(), this.productId()));
  }

  private run(request: Observable<TourismProduct>): void {
    this.working.set(true);
    this.error.set(null);
    request.subscribe({
      next: (product) => {
        this.working.set(false);
        this.saved.emit(product);
      },
      error: (error: HttpErrorResponse) => {
        this.working.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudo guardar la programación.'));
      },
    });
  }
}
