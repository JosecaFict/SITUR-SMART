import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  LucideArrowDown,
  LucideArrowRight,
  LucideArrowUp,
  LucideBedDouble,
  LucideBuilding2,
  LucideCalendarCheck,
  LucideCircleAlert,
  LucideCreditCard,
  LucideLoaderCircle,
  LucideMapPin,
  LucideRefreshCw,
  LucideStar,
  LucideTag,
  LucideUsers,
  LucideX,
} from '@lucide/angular';
import { DashboardStats } from '../../../core/dashboard/dashboard-stats.models';
import { DashboardStatsService } from '../../../core/dashboard/dashboard-stats.service';

export interface PanelCompany {
  id: number;
  name: string;
}

interface Bar {
  label: string;
  values: { value: number; text: string; height: number; color: string; title: string }[];
}

/** Colores fijos por empresa en la comparación (máximo cuatro). */
export const COMPARE_COLORS = ['#0f766e', '#f59e0b', '#6366f1', '#ec4899'];
const STATE_COLORS: Record<string, string> = {
  CONFIRMADA: '#0f766e',
  COMPLETADA: '#2dd4bf',
  PAGO_PARCIAL: '#38bdf8',
  CREADA: '#f59e0b',
  CANCELADA: '#f87171',
  EXPIRADA_LIBERADA: '#94a3b8',
};
const STATE_LABELS: Record<string, string> = {
  CONFIRMADA: 'Confirmada',
  COMPLETADA: 'Completada',
  PAGO_PARCIAL: 'Pago parcial',
  CREADA: 'Pendiente de pago',
  CANCELADA: 'Cancelada',
  EXPIRADA_LIBERADA: 'Vencida',
};
const MAX_COMPARED = 4;
const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

/**
 * Indicadores de negocio del dashboard: ventas, reservas, ocupación y opinión.
 * La empresa ve los suyos; el SuperAdmin ve la plataforma y puede elegir
 * una empresa (filtra) o de dos a cuatro (compara lado a lado).
 */
@Component({
  selector: 'app-panel-negocio',
  imports: [
    DatePipe,
    DecimalPipe,
    RouterLink,
    LucideArrowDown,
    LucideArrowRight,
    LucideArrowUp,
    LucideBedDouble,
    LucideBuilding2,
    LucideCalendarCheck,
    LucideCircleAlert,
    LucideCreditCard,
    LucideLoaderCircle,
    LucideMapPin,
    LucideRefreshCw,
    LucideStar,
    LucideTag,
    LucideUsers,
    LucideX,
  ],
  templateUrl: './panel-negocio.html',
})
export class PanelNegocio {
  private readonly service = inject(DashboardStatsService);

  /** Empresa activa (vista de empresa) o null (SuperAdmin). */
  readonly tenantId = input<number | null>(null);
  readonly platform = input(false);
  /** Empresas que el SuperAdmin puede elegir para filtrar o comparar. */
  readonly companies = input<PanelCompany[]>([]);

  protected readonly stats = signal<DashboardStats | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly selected = signal<number[]>([]);
  protected readonly pickerOpen = signal(false);
  protected readonly colors = COMPARE_COLORS;
  protected readonly maxCompared = MAX_COMPARED;

  protected readonly comparing = computed(() => (this.stats()?.comparacion?.length ?? 0) >= 2);
  protected readonly selectedNames = computed(() => {
    const names = new Map(this.companies().map((c) => [c.id, c.name]));
    return this.selected().map((id) => ({ id, name: names.get(id) ?? `Empresa ${id}` }));
  });

  /** Barras de 6 meses: cobrado y reembolsado (plataforma) o neto y reservas (empresa). */
  protected readonly bars = computed<Bar[]>(() => {
    const data = this.stats();
    if (!data) return [];
    if (this.comparing()) {
      const rows = data.comparacion ?? [];
      const max = Math.max(1, ...rows.flatMap((row) => row.serie.map((m) => Number(m.neto))));
      return (rows[0]?.serie ?? []).map((month, index) => ({
        label: month.etiqueta,
        values: rows.map((row, i) => {
          const value = Number(row.serie[index]?.neto ?? 0);
          return {
            value,
            text: this.compact(value),
            height: this.height(value, max),
            color: COMPARE_COLORS[i % COMPARE_COLORS.length],
            title: `${row.nombre}: Bs ${value.toFixed(2)}`,
          };
        }),
      }));
    }
    const serie = data.finanzas.serie;
    if (this.platform()) {
      const max = Math.max(1, ...serie.map((m) => Number(m.cobrado)));
      return serie.map((m) => ({
        label: m.etiqueta,
        values: [
          { value: Number(m.cobrado), text: this.compact(Number(m.cobrado)), height: this.height(Number(m.cobrado), max), color: '#0f766e', title: `Cobrado: Bs ${m.cobrado}` },
          { value: Number(m.reembolsado), text: this.compact(Number(m.reembolsado)), height: this.height(Number(m.reembolsado), max), color: '#fca5a5', title: `Reembolsado: Bs ${m.reembolsado}` },
        ],
      }));
    }
    const maxMoney = Math.max(1, ...serie.map((m) => Number(m.neto)));
    const maxCount = Math.max(1, ...serie.map((m) => m.reservas));
    return serie.map((m) => ({
      label: m.etiqueta,
      values: [
        { value: Number(m.neto), text: this.compact(Number(m.neto)), height: this.height(Number(m.neto), maxMoney), color: '#0f766e', title: `Ingreso neto: Bs ${m.neto}` },
        { value: m.reservas, text: String(m.reservas), height: this.height(m.reservas, maxCount), color: '#2dd4bf', title: `Reservas: ${m.reservas}` },
      ],
    }));
  });

  protected readonly legend = computed(() => {
    if (this.comparing()) {
      return (this.stats()?.comparacion ?? []).map((row, i) => ({ label: row.nombre, color: COMPARE_COLORS[i % COMPARE_COLORS.length] }));
    }
    return this.platform()
      ? [{ label: 'Cobrado', color: '#0f766e' }, { label: 'Reembolsado', color: '#fca5a5' }]
      : [{ label: 'Ingreso neto (Bs)', color: '#0f766e' }, { label: 'Reservas', color: '#2dd4bf' }];
  });

  protected readonly cityMax = computed(() => Math.max(1, ...(this.stats()?.ciudades ?? []).map((c) => c.reservas)));
  protected readonly planMax = computed(() => Math.max(1, ...(this.stats()?.suscripciones ?? []).map((p) => p.empresas)));

  constructor() {
    effect(() => {
      this.tenantId();
      this.platform();
      untracked(() => this.load());
    });
  }

  protected load(): void {
    if (!this.platform() && !this.tenantId()) return;
    this.loading.set(true);
    this.error.set(null);
    this.service.get(this.platform() ? null : this.tenantId(), this.platform() ? this.selected() : []).subscribe({
      next: (data) => {
        this.stats.set(data);
        this.loading.set(false);
      },
      error: (err) => {
        this.loading.set(false);
        this.error.set(
          err?.status === 403
            ? 'Tu rol no tiene permiso para ver los indicadores de ventas.'
            : 'No se pudieron cargar los indicadores. Intenta de nuevo.',
        );
      },
    });
  }

  protected toggleCompany(id: number): void {
    const current = this.selected();
    if (current.includes(id)) {
      this.selected.set(current.filter((item) => item !== id));
    } else if (current.length < MAX_COMPARED) {
      this.selected.set([...current, id]);
    } else {
      return;
    }
    this.load();
  }

  protected clearSelection(): void {
    if (!this.selected().length) return;
    this.selected.set([]);
    this.load();
  }

  protected isSelected(id: number): boolean {
    return this.selected().includes(id);
  }

  protected stateColor(state: string): string {
    return STATE_COLORS[state] ?? '#94a3b8';
  }

  protected stateLabel(state: string): string {
    return STATE_LABELS[state] ?? state;
  }

  protected stateBadge(state: string): string {
    if (state === 'CONFIRMADA' || state === 'COMPLETADA') return 'bg-emerald-50 text-emerald-700';
    if (state === 'CANCELADA') return 'bg-red-50 text-red-700';
    if (state === 'CREADA' || state === 'PAGO_PARCIAL') return 'bg-amber-50 text-amber-800';
    return 'bg-slate-100 text-slate-600';
  }

  protected alertClass(level: string): string {
    if (level === 'alta') return 'border-red-200 bg-red-50 text-red-800';
    if (level === 'media') return 'border-amber-200 bg-amber-50 text-amber-900';
    return 'border-sky-200 bg-sky-50 text-sky-900';
  }

  protected stars(value: number | null): number[] {
    const full = Math.round(value ?? 0);
    return [1, 2, 3, 4, 5].map((n) => (n <= full ? 1 : 0));
  }

  /** "2026-11-26T15:00:00-04:00" -> "26 nov" o "26 nov, 15:00" (hora local del navegador). */
  protected shortDate(iso: string, withTime = false): string {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return '';
    const day = `${date.getDate()} ${MONTHS[date.getMonth()]}`;
    if (!withTime) return day;
    const time = `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
    return `${day}, ${time}`;
  }

  protected money(value: string | number): string {
    return Number(value).toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  private compact(value: number): string {
    if (value >= 1000) return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k`;
    return value % 1 === 0 ? String(value) : value.toFixed(0);
  }

  private height(value: number, max: number): number {
    if (!value) return 2;
    return Math.max(4, Math.round((value / max) * 100));
  }
}
