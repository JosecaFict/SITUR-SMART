import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { LucideCircleAlert, LucideCreditCard, LucideRefreshCw } from '@lucide/angular';
import { AuthService } from '../../../core/auth/auth.service';
import { Plan } from '../../../core/companies/companies.models';
import { CompaniesService } from '../../../core/companies/companies.service';
import { apiErrorMessage } from '../../../core/http/api-error';
import { MyPlan, MyPlanService } from '../../../core/subscription/my-plan.service';

const STATE_LABELS: Record<string, string> = {
  ACTIVA: 'Vigente',
  POR_VENCER: 'Por vencer',
  VENCIDA: 'Vencido',
  CANCELADA: 'Cancelado',
  SUSPENDIDA: 'Suspendido',
  SIN_PLAN: 'Sin plan',
};

/**
 * Plan de la empresa: vigencia, uso de los límites, renovación automática y
 * pago de la renovación (o de otro plan) con Stripe.
 */
@Component({
  selector: 'situr-mi-plan',
  imports: [DatePipe, LucideCircleAlert, LucideCreditCard, LucideRefreshCw],
  templateUrl: './mi-plan.html',
})
export class MiPlan implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly service = inject(MyPlanService);
  private readonly companies = inject(CompaniesService);

  protected readonly plan = signal<MyPlan | null>(null);
  protected readonly plans = signal<Plan[]>([]);
  protected readonly loading = signal(true);
  protected readonly paying = signal(false);
  protected readonly savingRenew = signal(false);
  protected readonly selectedPlan = signal<string>('');
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  private readonly tenantId = computed(() => this.auth.session()?.user.tenants[0]?.id ?? null);
  protected readonly stateLabel = computed(() => STATE_LABELS[this.plan()?.estado ?? 'SIN_PLAN']);

  ngOnInit(): void {
    const result = this.route.snapshot.queryParamMap.get('pago');
    if (result === 'exito') this.notice.set('¡Pago recibido! Tu plan ya está actualizado.');
    if (result === 'cancelado') this.notice.set('El pago no se completó. No se cobró nada.');
    this.companies.listPlans().subscribe({
      next: (plans) => this.plans.set(plans.filter((plan) => plan.activo)),
      error: () => this.plans.set([]),
    });
    this.load();
  }

  protected load(): void {
    const tenantId = this.tenantId();
    if (tenantId === null) {
      this.loading.set(false);
      this.error.set('Tu cuenta no tiene una empresa asignada.');
      return;
    }
    this.service.get(tenantId).subscribe({
      next: (plan) => {
        this.plan.set(plan);
        this.selectedPlan.set(plan.plan?.codigo ?? '');
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudo cargar tu plan.'));
      },
    });
  }

  protected toggleRenew(): void {
    const tenantId = this.tenantId();
    const current = this.plan();
    if (tenantId === null || !current || this.savingRenew()) return;
    this.savingRenew.set(true);
    this.service.setAutoRenew(tenantId, !current.renovacion_automatica).subscribe({
      next: (plan) => {
        this.plan.set(plan);
        this.savingRenew.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.savingRenew.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudo cambiar la renovación automática.'));
      },
    });
  }

  protected pay(): void {
    const tenantId = this.tenantId();
    if (tenantId === null || this.paying()) return;
    this.paying.set(true);
    this.error.set(null);
    const code = this.selectedPlan();
    this.service.pay(tenantId, code && code !== this.plan()?.plan?.codigo ? code : undefined).subscribe({
      // Stripe Checkout: al terminar vuelve a /mi-plan?pago=exito.
      next: ({ checkout_url }) => window.location.assign(checkout_url),
      error: (error: HttpErrorResponse) => {
        this.paying.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudo iniciar el pago.'));
      },
    });
  }

  protected selectPlan(event: Event): void {
    this.selectedPlan.set((event.target as HTMLSelectElement).value);
  }

  protected selectedPrice(): string {
    const plan = this.plans().find((item) => item.codigo === this.selectedPlan());
    if (plan) return `${plan.moneda} ${plan.precio}`;
    const current = this.plan()?.plan;
    return current ? `${current.moneda} ${current.precio_renovacion}` : '';
  }

  protected usagePercent(usado: number, limite: number): number {
    return limite > 0 ? Math.min(100, Math.round((usado / limite) * 100)) : 0;
  }

  protected periodLabel(value: string | undefined): string {
    return value === 'ANUAL' ? 'anual' : 'mensual';
  }
}
