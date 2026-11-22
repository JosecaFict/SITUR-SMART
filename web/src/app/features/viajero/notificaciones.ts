import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';
import { LucideBadgePercent, LucideBell, LucideSparkles } from '@lucide/angular';
import { Subscription } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { senderName } from '../../core/communications/communications.models';
import { WebPushService } from '../../core/notifications/web-push.service';
import { apiErrorMessage } from '../../core/http/api-error';
import { AppNotification, CustomerInterests } from '../../core/traveler/traveler.models';
import { TravelerService } from '../../core/traveler/traveler.service';
import { CommunicationPreferences } from '../../shared/communication-preferences/communication-preferences';

const OFFER_KIND = 'OFERTA_INTERES';

/**
 * Bandeja de la cuenta: comunicaciones para personal y clientes, reservas y ofertas.
 * Solo el viajero consulta sus intereses y navega a sus reservas personales.
 */
@Component({
  selector: 'situr-notificaciones',
  imports: [DatePipe, RouterLink, LucideBadgePercent, LucideBell, LucideSparkles, CommunicationPreferences],
  template: `
    <section class="inbox mx-auto max-w-4xl space-y-5">
      <header class="inbox-hero flex flex-wrap items-end justify-between gap-3">
        <div>
          <p class="text-sm font-bold tracking-widest uppercase">{{ isCustomer() ? 'Tu próxima experiencia empieza aquí' : 'Tu equipo, conectado' }}</p>
          <h1 class="font-heading mt-2 text-3xl font-bold tracking-tight">Notificaciones</h1>
          <p class="mt-3 max-w-xl">{{ isCustomer() ? 'Indicaciones para tus viajes, novedades y experiencias que pueden interesarte.' : 'Avisos de coordinación y novedades de las empresas con las que trabajas.' }}</p>
          <span class="unread-pill">{{ traveler.unread() }} sin leer</span>
        </div>
        @if (traveler.unread() > 0) {
          <button type="button" class="secondary-button" (click)="markAll()" [disabled]="markingAll() || reading().length > 0">Marcar todas como leídas</button>
        }
      </header>

      <details class="inbox-settings border-input-border rounded-2xl border bg-white p-5">
      <summary class="font-semibold cursor-pointer">Configura cómo recibes tus avisos</summary>
      <article class="mt-5 space-y-3" aria-labelledby="browser-notifications-title">
        <h2 id="browser-notifications-title" class="text-title font-bold">Avisos en este navegador</h2>
        <p class="text-text-secondary text-sm" role="status">{{ pushMessage() }}</p>
        @if (push.error(); as text) { <p role="alert" class="text-sm text-red-700">{{ text }}</p> }
        @if (push.enabled()) {
          <button type="button" class="secondary-button" [disabled]="push.busy()" (click)="push.deactivate()">Desactivar avisos del navegador</button>
        } @else if (push.supported() && push.config()?.habilitado && push.permission() !== 'denied') {
          <button type="button" class="secondary-button" [disabled]="push.busy()" (click)="push.activate()">Activar avisos del navegador</button>
        } @else if (push.status() === 'unavailable' || push.status() === 'error') {
          <button type="button" class="secondary-button" [disabled]="push.busy()" (click)="push.loadConfig()">Reintentar configuración</button>
        }
      </article>

      <situr-communication-preferences />
      </details>
      @if (isCustomer()) {
      <article class="border-input-border rounded-2xl border bg-white p-5 shadow-sm" aria-label="Mis intereses">
        <h2 class="text-title flex items-center gap-2 font-bold"><svg lucideSparkles class="text-accent-dark h-5 w-5"></svg>Mis intereses</h2>
        @if (interests(); as profile) {
          @if (hasInterests()) {
            <p class="text-text-secondary mt-1 text-sm">
              Te avisamos de ofertas que encajan con esto. Lo calculamos con
              {{ profile.basado_en.favoritos }} favoritos, {{ profile.basado_en.reservas }} reservas y {{ profile.basado_en.resenas }} reseñas.
            </p>
            <div class="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <p class="text-label text-xs font-semibold">Destinos</p>
                <ul class="mt-2 space-y-2">
                  @for (city of profile.ciudades; track city.nombre) {
                    <li>
                      <div class="flex justify-between text-sm"><span class="text-title">{{ city.nombre }}</span><span class="text-text-secondary">{{ city.puntaje }}%</span></div>
                      <div class="bg-input-bg mt-1 h-1.5 overflow-hidden rounded-full"><div class="bg-accent h-full rounded-full" [style.width.%]="city.puntaje"></div></div>
                    </li>
                  }
                </ul>
              </div>
              <div>
                <p class="text-label text-xs font-semibold">Tipo de experiencia</p>
                <ul class="mt-2 space-y-2">
                  @for (type of profile.tipos; track type.nombre) {
                    <li>
                      <div class="flex justify-between text-sm"><span class="text-title">{{ type.nombre }}</span><span class="text-text-secondary">{{ type.puntaje }}%</span></div>
                      <div class="bg-input-bg mt-1 h-1.5 overflow-hidden rounded-full"><div class="bg-accent h-full rounded-full" [style.width.%]="type.puntaje"></div></div>
                    </li>
                  }
                </ul>
              </div>
            </div>
          } @else {
            <p class="text-text-secondary mt-1 text-sm">
              Todavía no sabemos qué te interesa. Guarda lugares en favoritos o haz una reserva y te avisaremos de ofertas que te encajen.
            </p>
          }
        } @else {
          <p class="text-text-secondary mt-1 text-sm">Cargando tus intereses…</p>
        }
      </article>
      }

      @if (error(); as text) { <p role="alert" class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{{ text }}</p><button type="button" class="secondary-button" (click)="load(1)" [disabled]="loading()">Volver a cargar</button> }
      @if (loading()) { <p role="status" class="text-text-secondary text-sm">Cargando avisos…</p> }
      @if (items().length === 0 && !loading() && !error()) {
        <div class="border-input-border rounded-2xl border border-dashed bg-white px-6 py-16 text-center">
          <svg lucideBell class="text-text-secondary mx-auto h-10 w-10"></svg>
          <p class="text-title mt-3 font-semibold">No tienes avisos</p>
        </div>
      }
      <h2 class="text-xl font-bold text-title">Tu bandeja</h2>
      <ul class="space-y-4">
        @for (item of items(); track item.id) {
          <li>
            <button type="button" (click)="open(item)" class="inbox-message border-input-border w-full rounded-2xl border bg-white p-6 text-left transition hover:shadow-sm"
              [disabled]="markingAll() || reading().includes(item.id)" [attr.aria-busy]="reading().includes(item.id)"
              [class.border-l-4]="!item.leida" [class.border-l-accent]="!item.leida">
              @if (isCommunication(item)) {
                <span class="bg-demo-bg text-accent-dark mb-2 inline-flex rounded-full px-3 py-1 text-sm font-semibold">Comunicación · {{ item.datos.tipo_comunicacion === 'INTERNA' ? 'Equipo' : item.datos.tipo_comunicacion === 'PROMOCIONAL' ? 'Promoción' : 'Información' }}</span>
                <p class="text-label mb-1 text-sm">De: {{ senderName(item.datos.remitente) }}</p>
              }
              @if (isOffer(item)) {
                <span class="bg-demo-bg text-accent-dark mb-1 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-bold">
                  <svg lucideBadgePercent class="h-3.5 w-3.5"></svg>Oferta para ti
                </span>
              }
              <p class="text-title text-xl font-semibold mb-3">{{ item.titulo }}</p>
              @if (item.datos.vence_en) { <p class="text-xs text-text-secondary">{{ expired(item) ? 'Oferta o aviso vencido' : 'Válido hasta' }} · {{ item.datos.vence_en | date: 'dd/MM/yyyy HH:mm' }}</p> }
              <p class="text-label whitespace-pre-wrap break-words text-base leading-relaxed">{{ item.mensaje }}</p>
              <p class="text-text-secondary mt-4 border-t border-input-border pt-3 text-sm">{{ item.creado_en | date: 'dd/MM/yyyy HH:mm' }} · {{ item.leida ? 'Leída' : 'Sin leer · pulsa para marcar como leída' }}</p>
            </button>
            @if (isCommunication(item) && item.datos.reserva_id && isCustomer()) {
              <a class="text-accent-dark mt-2 inline-block px-4 text-sm font-semibold underline" [routerLink]="['/mis-viajes', item.datos.reserva_id]">Ver reserva</a>
            }
            @if (item.datos.promocion_id && !expired(item)) {
              <a class="text-accent-dark mt-2 inline-block px-4 text-sm font-semibold underline" [routerLink]="['/marketplace/promociones', item.datos.promocion_id]">Ver oferta</a>
            }
          </li>
        }
      </ul>
      @if (hasMore()) {
        <button type="button" class="secondary-button" (click)="load(page() + 1)" [disabled]="loading()">Ver más</button>
      }
    </section>
  `,
  styles: [`
    .inbox {font-size:16px;line-height:1.6}
    .inbox-hero {background:#104f40;color:#fff;padding:30px;border-radius:22px}
    .inbox-hero>div>p:first-child {color:#bde5cc;font-size:14px}
    .inbox-hero .secondary-button {background:#fff;color:#245c41;border-color:#d1e4d7}
    .unread-pill {display:inline-block;margin-top:18px;background:#ffffff18;border:1px solid #ffffff30;border-radius:20px;padding:4px 12px;font-size:14px}
    .inbox-message {box-shadow:0 3px 16px #1c4e3410}
    .inbox-message:focus-visible {outline:3px solid #56a57d;outline-offset:3px}
    .inbox-settings summary {color:#2e644a}
    @media(max-width:540px){.inbox-hero{padding:23px}.inbox-message{padding:20px}}
  `],
})
export class Notificaciones implements OnInit {
  protected readonly traveler = inject(TravelerService);
  protected readonly push = inject(WebPushService);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);
  private request?: Subscription;
  protected readonly senderName = senderName;
  protected readonly isCustomer = computed(() => {
    const user = this.auth.session()?.user;
    return !!user && !user.roles.includes('SUPER_ADMIN') && !user.tenants.length;
  });

  protected readonly items = signal<AppNotification[]>([]);
  protected readonly loading = signal(true);
  protected readonly hasMore = signal(false);
  protected readonly page = signal(1);
  protected readonly error = signal<string | null>(null);
  protected readonly reading = signal<number[]>([]);
  protected readonly markingAll = signal(false);
  protected readonly interests = signal<CustomerInterests | null>(null);
  protected readonly hasInterests = computed(() => {
    const profile = this.interests();
    return !!profile && (profile.ciudades.length > 0 || profile.tipos.length > 0);
  });

  ngOnInit(): void {
    this.load(1);
    this.refreshUnread();
    void this.push.loadConfig().then(() => this.push.restore());
    this.push.foregroundMessages$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
      this.load(1);
      this.refreshUnread();
    });
    if (!this.isCustomer()) return;
    this.traveler.interests().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (profile) => this.interests.set(profile),
      error: () => this.interests.set({ ciudades: [], tipos: [], basado_en: { favoritos: 0, reservas: 0, resenas: 0 } }),
    });
  }

  protected load(page: number): void {
    this.request?.unsubscribe();
    this.loading.set(true);
    this.error.set(null);
    this.request = this.traveler.notifications(page).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (result) => {
        this.items.update((list) => (page === 1 ? result.results : [...list, ...result.results]));
        this.hasMore.set(!!result.next);
        this.page.set(page);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudieron cargar tus avisos.'));
      },
    });
  }

  protected isOffer(item: AppNotification): boolean {
    return item.tipo === OFFER_KIND || item.datos.tipo_comunicacion === 'PROMOCIONAL';
  }

  protected expired(item: AppNotification): boolean {
    return !!item.datos.vence_en && new Date(item.datos.vence_en).getTime() <= Date.now();
  }

  protected isCommunication(item: AppNotification): boolean {
    return item.tipo === 'COMUNICACION' || item.datos?.motivo === 'COMUNICACION';
  }

  protected pushMessage(): string {
    if (this.push.busy()) return 'Actualizando los avisos de este navegador…';
    if (!this.push.supported()) return 'Este navegador no admite avisos push. Puedes leer tus mensajes en esta bandeja.';
    if (this.push.permission() === 'denied') return 'Los avisos están bloqueados. Puedes permitirlos desde la configuración del sitio en tu navegador.';
    if (this.push.enabled()) return 'Los avisos están activos para tu cuenta en este navegador.';
    if (!this.push.config()?.habilitado) return 'Los avisos del navegador aún no están disponibles. Puedes leer tus mensajes aquí.';
    return 'Activa los avisos para recibir notificaciones en este navegador. Te pediremos permiso al pulsar el botón.';
  }

  private refreshUnread(): void {
    this.traveler.refreshUnread().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({ error: () => undefined });
  }

  protected open(item: AppNotification): void {
    if (this.markingAll() || this.reading().includes(item.id)) return;
    this.error.set(null);
    if (!item.leida) {
      this.reading.update((ids) => [...ids, item.id]);
      this.traveler.markRead(item.id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
        next: () => {
          this.items.update((list) => list.map((n) => n.id === item.id ? { ...n, leida: true } : n));
          this.reading.update((ids) => ids.filter((id) => id !== item.id));
          this.refreshUnread();
          this.navigate(item);
        },
        error: (error: HttpErrorResponse) => {
          this.reading.update((ids) => ids.filter((id) => id !== item.id));
          this.error.set(apiErrorMessage(error, 'No se pudo marcar el aviso como leído.'));
        },
      });
      return;
    }
    this.navigate(item);
  }

  private navigate(item: AppNotification): void {
    if (this.isCommunication(item) || !this.isCustomer()) return;
    if (item.datos?.promocion_id && !this.expired(item)) {
      this.router.navigate(['/marketplace/promociones', item.datos.promocion_id]);
    } else if (item.datos?.reserva_id) {
      this.router.navigate(['/mis-viajes', item.datos.reserva_id]);
    }
  }

  protected markAll(): void {
    if (this.markingAll() || this.reading().length) return;
    this.markingAll.set(true);
    this.error.set(null);
    this.traveler.markAllRead().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.items.update((list) => list.map((n) => ({ ...n, leida: true })));
        this.markingAll.set(false);
        this.refreshUnread();
      },
      error: (error: HttpErrorResponse) => {
        this.markingAll.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudieron marcar los avisos como leídos.'));
      },
    });
  }
}
