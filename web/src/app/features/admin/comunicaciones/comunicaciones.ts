import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subject, Subscription, debounceTime } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { communicationScope } from '../../../core/communications/communication-scope';
import { CommunicationPage, senderName } from '../../../core/communications/communications.models';
import { CommunicationsService } from '../../../core/communications/communications.service';
import { apiErrorMessage } from '../../../core/http/api-error';

@Component({
  selector: 'situr-comunicaciones',
  imports: [DatePipe, RouterLink],
  templateUrl: './comunicaciones.html',
  styleUrls: ['./communication-shared.css', './comunicaciones.css'],
})
export class Comunicaciones implements OnInit {
  private readonly service = inject(CommunicationsService);
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly searchChanges = new Subject<void>();
  private request?: Subscription;

  protected readonly tenants = signal((this.auth.session()?.user.tenants ?? []).map((tenant) => ({ id: tenant.id, name: tenant.name })));
  protected readonly isGlobalAdmin = this.auth.session()?.user.roles.includes('SUPER_ADMIN') ?? false;
  protected readonly tenantId = signal<number | undefined>(undefined);
  protected readonly ready = signal(false);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly result = signal<CommunicationPage | null>(null);
  protected readonly searchText = signal('');
  protected readonly stateFilter = signal('');
  protected readonly filters = [
    { value: '', label: 'Todas' }, { value: 'BORRADOR', label: 'Borradores' },
    { value: 'PROGRAMADA', label: 'Programadas' }, { value: 'PUBLICADA', label: 'Publicadas' },
    { value: 'REVISION', label: 'Por revisar' }, { value: 'CANCELADA', label: 'Canceladas' },
  ];
  protected readonly page = signal(1);
  protected readonly senderName = senderName;

  ngOnInit(): void {
    this.searchChanges.pipe(debounceTime(250), takeUntilDestroyed(this.destroyRef)).subscribe(() => this.load(1));
    try {
      this.tenantId.set(communicationScope(this.auth.session()?.user, this.route.snapshot.queryParamMap.get('empresa')));
      this.ready.set(true);
      this.load();
      if (this.isGlobalAdmin) {
        this.service.options().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
          next: (options) => this.tenants.set(options.empresas.map((company) => ({ id: company.id, name: company.nombre }))),
          error: () => this.error.set('No se pudieron cargar las empresas del selector. Puedes actualizar la página para reintentar.'),
        });
      }
    } catch (error) {
      this.error.set((error as Error).message);
    }
  }

  protected changeCompany(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.tenantId.set(value ? Number(value) : undefined);
    this.load();
  }

  protected load(page = 1): void {
    if (!this.ready()) return;
    this.request?.unsubscribe();
    this.error.set(null);
    this.loading.set(true);
    this.result.set(null);
    const request = this.stateFilter() || this.searchText().trim()
      ? this.service.list(this.tenantId(), page, this.stateFilter(), this.searchText().trim())
      : this.service.list(this.tenantId(), page);
    this.request = request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (result) => { this.result.set(result); this.page.set(page); this.loading.set(false); },
      error: (error: HttpErrorResponse) => {
        this.error.set(apiErrorMessage(error, 'No se pudieron cargar las comunicaciones.'));
        this.loading.set(false);
      },
    });
  }
  protected filterBy(state: string): void { this.stateFilter.set(state); this.load(1); }
  protected search(event: Event): void { this.searchText.set((event.target as HTMLInputElement).value); this.searchChanges.next(); }
  protected summary(state: string): number {
    const result = this.result();
    return result?.resumen?.[state] ?? result?.results.filter((item) => item.estado === state).length ?? 0;
  }
  protected stateName(state: string): string {
    return ({ BORRADOR: 'Borrador', PROGRAMADA: 'Programada', PUBLICADA: 'Publicada', CANCELADA: 'Cancelada', VENCIDA: 'Vencida', REVISION: 'Por revisar' } as Record<string, string>)[state] ?? state;
  }

}
