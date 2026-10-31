import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import {
  LucideArrowLeft, LucideCircleAlert, LucideLanguages, LucidePencil, LucidePhone, LucidePlus,
  LucideUserCheck, LucideX,
} from '@lucide/angular';
import { AuthService } from '../../../core/auth/auth.service';
import { apiErrorMessage } from '../../../core/http/api-error';
import { Guide, GuidePayload } from '../../../core/tours/tours.models';
import { GuidesService } from '../../../core/tours/tours.service';

/** "Español, inglés" -> ["Español", "inglés"], sin vacíos ni repetidos. */
export function parseLanguages(text: string): string[] {
  const seen = new Set<string>();
  return text
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item && !seen.has(item.toLowerCase()) && seen.add(item.toLowerCase()));
}

/** Guías de la empresa, que se asignan a las salidas de los tours. */
@Component({
  selector: 'situr-guias',
  imports: [
    ReactiveFormsModule, LucideArrowLeft, LucideCircleAlert, LucideLanguages, LucidePencil, LucidePhone,
    LucidePlus, LucideUserCheck, LucideX,
  ],
  template: `
    <section class="mx-auto max-w-5xl space-y-6">
      <header class="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 class="font-heading text-title text-3xl font-bold tracking-tight">Guías</h1>
          <p class="text-text-secondary mt-1 text-sm sm:text-base">Las personas que acompañan tus tours. Asígnalas a cada salida.</p>
        </div>
        <div class="flex gap-2">
          <button type="button" (click)="backToTours()" class="border-input-border hover:bg-input-bg flex items-center gap-2 rounded-xl border bg-white px-4 py-2.5 text-sm font-semibold text-label">
            <svg lucideArrowLeft class="h-4 w-4"></svg>Tours
          </button>
          @if (canManage() && !formOpen()) {
            <button type="button" (click)="startCreate()" class="bg-accent hover:bg-accent-dark flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white">
              <svg lucidePlus class="h-4 w-4"></svg>Nuevo guía
            </button>
          }
        </div>
      </header>

      @if (successMessage(); as message) {
        <div class="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <span>{{ message }}</span>
          <button type="button" (click)="successMessage.set(null)" aria-label="Cerrar mensaje"><svg lucideX class="h-4 w-4"></svg></button>
        </div>
      }
      @if (errorMessage(); as message) {
        <div class="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
          <svg lucideCircleAlert class="mt-0.5 h-4 w-4 shrink-0"></svg><span>{{ message }}</span>
        </div>
      }

      @if (formOpen()) {
        <form [formGroup]="form" (ngSubmit)="save()" class="border-input-border grid gap-4 rounded-2xl border bg-white p-5 shadow-sm sm:grid-cols-3">
          <h2 class="text-sm font-bold text-title sm:col-span-3">{{ editing() ? 'Editar guía' : 'Nuevo guía' }}</h2>
          <label class="flex flex-col gap-1.5 text-sm font-semibold text-label">Nombre completo
            <input formControlName="nombres" placeholder="Ej. Marcelo Choque" class="border-input-border rounded-xl border px-3.5 py-2.5 font-normal text-title outline-none focus:border-accent-dark focus:ring-4 focus:ring-accent/15" />
          </label>
          <label class="flex flex-col gap-1.5 text-sm font-semibold text-label">Teléfono
            <input formControlName="telefono" placeholder="Ej. +591 71234567" class="border-input-border rounded-xl border px-3.5 py-2.5 font-normal text-title outline-none focus:border-accent-dark focus:ring-4 focus:ring-accent/15" />
          </label>
          <label class="flex flex-col gap-1.5 text-sm font-semibold text-label">Idiomas
            <input formControlName="idiomas" placeholder="Español, inglés" class="border-input-border rounded-xl border px-3.5 py-2.5 font-normal text-title outline-none focus:border-accent-dark focus:ring-4 focus:ring-accent/15" />
            <span class="text-xs font-normal text-text-secondary">Separados por coma.</span>
          </label>
          @if (formError(); as message) { <p class="text-sm font-semibold text-red-700 sm:col-span-3" role="alert">{{ message }}</p> }
          <div class="flex justify-end gap-2 sm:col-span-3">
            <button type="button" (click)="closeForm()" class="border-input-border hover:bg-input-bg rounded-xl border px-4 py-2 text-sm font-semibold text-label">Cancelar</button>
            <button type="submit" [disabled]="saving()" class="bg-accent hover:bg-accent-dark rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">{{ saving() ? 'Guardando…' : 'Guardar' }}</button>
          </div>
        </form>
      }

      @if (loading()) {
        <div class="h-48 animate-pulse rounded-2xl bg-gray-200"></div>
      } @else if (guides().length === 0) {
        <div class="border-input-border rounded-2xl border bg-white px-6 py-14 text-center shadow-sm">
          <span class="bg-demo-bg text-accent-dark mx-auto flex h-14 w-14 items-center justify-center rounded-2xl"><svg lucideUserCheck class="h-7 w-7"></svg></span>
          <p class="font-heading mt-4 text-lg font-bold text-title">Todavía no registraste guías</p>
          <p class="mt-1 text-sm text-text-secondary">Son opcionales: una salida puede no tener guía asignado.</p>
        </div>
      } @else {
        <ul class="border-input-border divide-y divide-input-border overflow-hidden rounded-2xl border bg-white shadow-sm">
          @for (guide of guides(); track guide.id) {
            <li class="flex flex-wrap items-center gap-4 p-4" [class.opacity-60]="guide.estado === 'INACTIVO'">
              <span class="bg-demo-bg text-accent-dark flex h-10 w-10 items-center justify-center rounded-full font-bold">{{ guide.nombres.charAt(0) }}</span>
              <div class="min-w-48 flex-1">
                <p class="font-semibold text-title">{{ guide.nombres }}</p>
                <p class="mt-0.5 flex flex-wrap gap-3 text-xs text-text-secondary">
                  @if (guide.telefono) { <span class="flex items-center gap-1"><svg lucidePhone class="h-3.5 w-3.5"></svg>{{ guide.telefono }}</span> }
                  @if (guide.idiomas.length) { <span class="flex items-center gap-1"><svg lucideLanguages class="h-3.5 w-3.5"></svg>{{ guide.idiomas.join(', ') }}</span> }
                </p>
              </div>
              <span class="rounded-full px-2.5 py-1 text-xs font-bold" [class]="guide.estado === 'ACTIVO' ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-700'">{{ guide.estado === 'ACTIVO' ? 'Activo' : 'Inactivo' }}</span>
              @if (canManage()) {
                <div class="flex gap-1">
                  <button type="button" (click)="startEdit(guide)" class="rounded-lg p-2 text-text-secondary hover:bg-input-bg" [attr.aria-label]="'Editar a ' + guide.nombres"><svg lucidePencil class="h-4 w-4"></svg></button>
                  <button type="button" (click)="toggleStatus(guide)" class="rounded-lg px-3 py-1.5 text-xs font-semibold" [class]="guide.estado === 'ACTIVO' ? 'text-red-600 hover:bg-red-50' : 'text-emerald-700 hover:bg-emerald-50'">
                    {{ guide.estado === 'ACTIVO' ? 'Desactivar' : 'Activar' }}
                  </button>
                </div>
              }
            </li>
          }
        </ul>
      }
    </section>
  `,
})
export class Guias implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly guidesService = inject(GuidesService);
  private readonly fb = inject(FormBuilder);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  protected readonly companyId = signal<number | null>(null);
  protected readonly guides = signal<Guide[]>([]);
  protected readonly loading = signal(true);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly successMessage = signal<string | null>(null);
  protected readonly formOpen = signal(false);
  protected readonly editing = signal<Guide | null>(null);
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);

  protected readonly canManage = computed(() => {
    const user = this.auth.session()?.user;
    return !!user && (user.roles.includes('SUPER_ADMIN') || user.permisos.includes('PRODUCTOS_GESTIONAR'));
  });

  protected readonly form = this.fb.nonNullable.group({
    nombres: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(150)]],
    telefono: ['', Validators.pattern(/^[0-9+()\- ]{6,30}$/)],
    idiomas: [''],
  });

  ngOnInit(): void {
    this.companyId.set(
      Number(this.route.snapshot.queryParamMap.get('empresa')) || this.auth.session()?.user.tenants[0]?.id || null,
    );
    this.load();
  }

  protected load(): void {
    const companyId = this.companyId();
    if (!companyId) {
      this.loading.set(false);
      this.errorMessage.set('No fue posible determinar la empresa.');
      return;
    }
    this.guidesService.list(companyId).subscribe({
      next: (guides) => { this.guides.set(guides); this.loading.set(false); },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible cargar los guías.'));
      },
    });
  }

  protected startCreate(): void {
    this.editing.set(null);
    this.form.reset({ nombres: '', telefono: '', idiomas: '' });
    this.formError.set(null);
    this.formOpen.set(true);
  }

  protected startEdit(guide: Guide): void {
    this.editing.set(guide);
    this.form.reset({ nombres: guide.nombres, telefono: guide.telefono ?? '', idiomas: guide.idiomas.join(', ') });
    this.formError.set(null);
    this.formOpen.set(true);
  }

  protected closeForm(): void {
    this.formOpen.set(false);
    this.editing.set(null);
  }

  protected save(): void {
    const companyId = this.companyId();
    if (!companyId) return;
    if (this.form.invalid) {
      this.formError.set(
        this.form.controls.telefono.invalid ? 'El teléfono solo admite números, espacios y + ( ) -.' : 'Escribe el nombre completo del guía.',
      );
      return;
    }
    const raw = this.form.getRawValue();
    const payload: GuidePayload = {
      nombres: raw.nombres.trim(),
      telefono: raw.telefono.trim() || null,
      idiomas: parseLanguages(raw.idiomas),
    };
    const editing = this.editing();
    this.saving.set(true);
    this.formError.set(null);
    const request = editing
      ? this.guidesService.update(companyId, editing.id, payload)
      : this.guidesService.create(companyId, payload);
    request.subscribe({
      next: (guide) => {
        this.saving.set(false);
        this.guides.update((items) =>
          editing ? items.map((item) => (item.id === guide.id ? guide : item)) : [...items, guide].sort((a, b) => a.nombres.localeCompare(b.nombres)),
        );
        this.closeForm();
        this.successMessage.set(editing ? 'Guía actualizado.' : 'Guía registrado.');
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.formError.set(apiErrorMessage(error, 'No fue posible guardar el guía.'));
      },
    });
  }

  protected toggleStatus(guide: Guide): void {
    const companyId = this.companyId();
    if (!companyId) return;
    this.errorMessage.set(null);
    this.successMessage.set(null);
    const request = guide.estado === 'ACTIVO'
      ? this.guidesService.deactivate(companyId, guide.id)
      : this.guidesService.update(companyId, guide.id, { estado: 'ACTIVO' });
    request.subscribe({
      next: (updated) => {
        this.guides.update((items) => items.map((item) => (item.id === updated.id ? updated : item)));
        this.successMessage.set(updated.estado === 'ACTIVO' ? 'Guía activado.' : 'Guía desactivado.');
      },
      error: (error: HttpErrorResponse) => this.errorMessage.set(apiErrorMessage(error, 'No fue posible cambiar el estado.')),
    });
  }

  protected backToTours(): void {
    this.router.navigate(['/tours'], { queryParams: this.companyId() ? { empresa: this.companyId() } : undefined });
  }
}
