import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { LucideBadgePercent, LucideCircleAlert, LucideEye, LucidePackageOpen, LucidePencil, LucidePlus, LucideSearch } from '@lucide/angular';
import { AuthService } from '../../../core/auth/auth.service';
import { Promotion, PromotionMode, PromotionState } from '../../../core/promotions/promotions.models';
import { promotionApiError, PromotionsService } from '../../../core/promotions/promotions.service';

const PAGE_SIZE = 10;

@Component({
  selector: 'situr-promociones',
  imports: [DatePipe, RouterLink, LucideBadgePercent, LucideCircleAlert, LucideEye, LucidePackageOpen, LucidePencil, LucidePlus, LucideSearch],
  templateUrl: './promociones.html',
  styleUrl: './promociones.css',
})
export class Promociones implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly service = inject(PromotionsService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  protected readonly tenants = this.auth.session()?.user.tenants ?? [];
  protected readonly tenantId = signal<number | null>(null);
  protected readonly canManage = computed(() => this.auth.session()?.user.permisos.includes('PRODUCTOS_GESTIONAR') ?? false);
  protected readonly items = signal<Promotion[]>([]);
  protected readonly loading = signal(true);
  protected readonly workingId = signal<number | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly success = signal<string | null>(null);
  protected readonly showChoice = signal(false);
  protected readonly searchTerm = signal('');
  protected readonly stateFilter = signal<PromotionState | ''>('');
  protected readonly modeFilter = signal<PromotionMode | ''>('');
  protected readonly page = signal(1);
  protected readonly filtered = computed(() => {
    const query = this.searchTerm().trim().toLocaleLowerCase('es');
    return this.items().filter((item) =>
      (!this.stateFilter() || item.estado === this.stateFilter()) &&
      (!this.modeFilter() || item.modalidad === this.modeFilter()) &&
      (!query || [item.nombre, item.empresa, item.descripcion].join(' ').toLocaleLowerCase('es').includes(query)));
  });
  protected readonly pageCount = computed(() => Math.max(1, Math.ceil(this.filtered().length / PAGE_SIZE)));
  protected readonly visible = computed(() => this.filtered().slice((this.page() - 1) * PAGE_SIZE, this.page() * PAGE_SIZE));
  protected readonly activeCount = computed(() => this.items().filter((item) => item.estado === 'VIGENTE').length);
  protected readonly draftCount = computed(() => this.items().filter((item) => item.estado === 'BORRADOR').length);

  ngOnInit(): void {
    const requested = Number(this.route.snapshot.queryParamMap.get('empresa'));
    this.tenantId.set(this.tenants.some((tenant) => tenant.id === requested) ? requested : (this.tenants[0]?.id ?? null));
    this.load();
  }

  protected changeTenant(event: Event): void {
    const value = Number((event.target as HTMLSelectElement).value);
    if (!this.tenants.some((tenant) => tenant.id === value)) return;
    this.tenantId.set(value);
    this.items.set([]);
    this.page.set(1);
    this.router.navigate([], { relativeTo: this.route, queryParams: { empresa: value }, replaceUrl: true });
    this.load();
  }

  protected load(): void {
    const tenant = this.tenantId();
    if (tenant === null) { this.loading.set(false); this.error.set('No tienes una empresa activa para consultar promociones.'); return; }
    this.loading.set(true);
    this.error.set(null);
    this.service.listCompany(tenant).subscribe({
      next: (items) => { if (this.tenantId() !== tenant) return; this.items.set(items); this.loading.set(false); },
      error: (error: HttpErrorResponse) => { if (this.tenantId() !== tenant) return; this.loading.set(false); this.error.set(promotionApiError(error)); },
    });
  }

  protected changeSearch(event: Event): void { this.searchTerm.set((event.target as HTMLInputElement).value); this.page.set(1); }
  protected changeState(event: Event): void { this.stateFilter.set((event.target as HTMLSelectElement).value as PromotionState | ''); this.page.set(1); }
  protected changeMode(event: Event): void { this.modeFilter.set((event.target as HTMLSelectElement).value as PromotionMode | ''); this.page.set(1); }
  protected next(): void { this.page.update((value) => Math.min(this.pageCount(), value + 1)); }
  protected previous(): void { this.page.update((value) => Math.max(1, value - 1)); }

  protected changePublication(item: Promotion): void {
    const tenant = this.tenantId();
    if (!this.canManage() || tenant === null || this.workingId() !== null) return;
    const disabling = item.estado_administrativo === 'HABILITADA';
    if (disabling && !confirm(`¿Desactivar la promoción «${item.nombre}»? Dejará de mostrarse públicamente.`)) return;
    this.workingId.set(item.id); this.error.set(null); this.success.set(null);
    const request = disabling ? this.service.deactivate(tenant, item.id) : this.service.publish(tenant, item.id);
    request.subscribe({
      next: (updated) => {
        this.items.update((items) => items.map((current) => current.id === updated.id ? updated : current));
        this.workingId.set(null);
        this.success.set(disabling ? 'Promoción desactivada.' : 'Promoción publicada.');
      },
      error: (error: HttpErrorResponse) => { this.workingId.set(null); this.error.set(promotionApiError(error, 'No se pudo cambiar el estado.')); },
    });
  }

  protected stateLabel(state: PromotionState): string {
    return ({ BORRADOR: 'Borrador', PROGRAMADA: 'Programada', VIGENTE: 'Vigente', DESACTIVADA: 'Desactivada', VENCIDA: 'Vencida' })[state];
  }
}
