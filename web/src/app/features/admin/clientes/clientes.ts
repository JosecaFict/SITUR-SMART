import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { LucideBan, LucideKeyRound, LucideLogOut, LucideSearch, LucideUnlock, LucideUsers, LucideX } from '@lucide/angular';
import {
  CustomerDetail,
  CustomerPage,
  CustomerRow,
  CustomerTotal,
  CustomersService,
} from '../../../core/customers/customers.service';
import { apiErrorMessage } from '../../../core/http/api-error';

type Action = 'bloquear' | 'desbloquear' | 'sesiones';

const ACTION_TEXT: Record<Action, { title: string; button: string; hint: string }> = {
  bloquear: {
    title: 'Bloquear la cuenta',
    button: 'Bloquear',
    hint: 'Se cierran sus sesiones en la web y el móvil, deja de recibir avisos y se cancelan sus reservas sin pagar. Las pagadas se mantienen. Le enviaremos el motivo por correo.',
  },
  desbloquear: {
    title: 'Desbloquear la cuenta',
    button: 'Desbloquear',
    hint: 'Podrá volver a iniciar sesión y reservar. Le avisaremos por correo.',
  },
  sesiones: {
    title: 'Cerrar sus sesiones',
    button: 'Cerrar sesiones',
    hint: 'Sale de todos sus dispositivos sin bloquear la cuenta (por ejemplo, si le robaron el celular).',
  },
};

const BOOKING_STATES: Record<string, string> = {
  CREADA: 'Pendiente de pago',
  PAGO_PARCIAL: 'Pago parcial',
  CONFIRMADA: 'Confirmada',
  COMPLETADA: 'Completada',
  CANCELADA: 'Cancelada',
  EXPIRADA_LIBERADA: 'Vencida',
};

const AUDIT_ACTIONS: Record<string, string> = {
  BLOQUEAR_CLIENTE: 'Bloqueo',
  DESBLOQUEAR_CLIENTE: 'Desbloqueo',
  CERRAR_SESIONES_CLIENTE: 'Cierre de sesiones',
  ENVIAR_RECUPERACION: 'Código de recuperación enviado',
};

/**
 * Cuentas de los turistas: la plataforma las ve, bloquea, desbloquea, les
 * cierra las sesiones y les envía el código de recuperación. No edita sus
 * datos personales: eso lo hace cada turista desde su perfil.
 */
@Component({
  selector: 'situr-clientes',
  imports: [DatePipe, LucideBan, LucideKeyRound, LucideLogOut, LucideSearch, LucideUnlock, LucideUsers, LucideX],
  templateUrl: './clientes.html',
})
export class Clientes implements OnInit {
  private readonly service = inject(CustomersService);

  protected readonly page = signal<CustomerPage | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly search = signal('');
  protected readonly status = signal('');
  protected readonly withBookings = signal('');
  protected readonly pageNumber = signal(1);

  protected readonly selected = signal<CustomerDetail | null>(null);
  protected readonly loadingDetail = signal(false);
  protected readonly action = signal<Action | null>(null);
  protected readonly reason = signal('');
  protected readonly working = signal(false);
  protected readonly detailMessage = signal<string | null>(null);
  protected readonly detailError = signal<string | null>(null);

  protected readonly actionText = ACTION_TEXT;

  ngOnInit(): void {
    this.load();
  }

  protected load(page = 1): void {
    this.loading.set(true);
    this.error.set(null);
    this.pageNumber.set(page);
    this.service
      .list({ buscar: this.search().trim(), estado: this.status(), con_reservas: this.withBookings(), page })
      .subscribe({
        next: (result) => {
          this.page.set(result);
          this.loading.set(false);
        },
        error: (error: HttpErrorResponse) => {
          this.loading.set(false);
          this.error.set(apiErrorMessage(error, 'No se pudieron cargar los clientes.'));
        },
      });
  }

  protected setFilter(signalName: 'search' | 'status' | 'withBookings', event: Event): void {
    const value = (event.target as HTMLInputElement | HTMLSelectElement).value;
    this[signalName].set(value);
    if (signalName !== 'search') this.load();
  }

  protected open(row: CustomerRow): void {
    this.loadingDetail.set(true);
    this.closeAction();
    this.detailMessage.set(null);
    this.detailError.set(null);
    this.service.detail(row.id).subscribe({
      next: (detail) => {
        this.selected.set(detail);
        this.loadingDetail.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loadingDetail.set(false);
        this.detailError.set(apiErrorMessage(error, 'No se pudo abrir la ficha del cliente.'));
      },
    });
  }

  protected closeDetail(): void {
    this.selected.set(null);
    this.closeAction();
  }

  protected startAction(action: Action): void {
    this.action.set(action);
    this.reason.set('');
    this.detailMessage.set(null);
    this.detailError.set(null);
  }

  protected closeAction(): void {
    this.action.set(null);
    this.reason.set('');
  }

  protected updateReason(event: Event): void {
    this.reason.set((event.target as HTMLTextAreaElement).value);
  }

  protected confirmAction(): void {
    const customer = this.selected();
    const action = this.action();
    const reason = this.reason().trim();
    if (!customer || !action || this.working()) return;
    if (reason.length < 5) {
      this.detailError.set('Explica el motivo (al menos 5 caracteres).');
      return;
    }
    this.working.set(true);
    const request =
      action === 'bloquear'
        ? this.service.block(customer.id, reason)
        : action === 'desbloquear'
          ? this.service.unblock(customer.id, reason)
          : this.service.closeSessions(customer.id, reason);
    request.subscribe({
      next: (detail) => {
        this.working.set(false);
        this.selected.set(detail);
        this.closeAction();
        this.detailMessage.set(
          action === 'bloquear'
            ? 'Cuenta bloqueada. Ya no puede entrar ni reservar.'
            : action === 'desbloquear'
              ? 'Cuenta desbloqueada.'
              : 'Sesiones cerradas en todos sus dispositivos.',
        );
        this.load(this.pageNumber());
      },
      error: (error: HttpErrorResponse) => {
        this.working.set(false);
        this.detailError.set(apiErrorMessage(error, 'No se pudo completar la acción.'));
      },
    });
  }

  protected sendReset(): void {
    const customer = this.selected();
    if (!customer || this.working()) return;
    this.working.set(true);
    this.service.sendPasswordReset(customer.id).subscribe({
      next: () => {
        this.working.set(false);
        this.detailMessage.set(`Le enviamos a ${customer.email} un código para recuperar su contraseña.`);
      },
      error: (error: HttpErrorResponse) => {
        this.working.set(false);
        this.detailError.set(apiErrorMessage(error, 'No se pudo enviar el código.'));
      },
    });
  }

  protected totals(values: CustomerTotal[]): string {
    return values.length ? values.map((value) => `${value.moneda} ${value.total}`).join(' · ') : '—';
  }

  protected bookingState(state: string): string {
    return BOOKING_STATES[state] ?? state;
  }

  protected auditAction(action: string): string {
    return AUDIT_ACTIONS[action] ?? action;
  }

  protected pages(): number {
    const result = this.page();
    return result ? Math.max(1, Math.ceil(result.count / 20)) : 1;
  }
}
