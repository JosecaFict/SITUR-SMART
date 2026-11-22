import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, ElementRef, Injector, OnInit, afterNextRender, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { Subject, catchError, debounceTime, forkJoin, map, of, switchMap } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { communicationScope } from '../../../core/communications/communication-scope';
import { AudienceGroup, AudiencePreview, Communication, CommunicationOption, CommunicationOptions, CommunicationPayload, CommunicationType, senderName } from '../../../core/communications/communications.models';
import { CommunicationsService } from '../../../core/communications/communications.service';
import { apiErrorMessage } from '../../../core/http/api-error';

type Selector = 'empresa_ids' | 'rol_ids' | 'usuario_ids';
type RemoteSource = 'usuarios' | 'reservas' | 'salidas' | 'promociones';
const GROUPS: { value: AudienceGroup; label: string }[] = [
  { value: 'TODOS', label: 'Todos' }, { value: 'PERSONAL', label: 'Todo el personal' },
  { value: 'CLIENTES', label: 'Clientes' }, { value: 'PROPIETARIOS', label: 'Propietarios' },
  { value: 'EMPLEADOS', label: 'Empleados' }, { value: 'USUARIOS', label: 'Usuarios seleccionados' },
];

@Component({
  selector: 'situr-comunicacion-editor',
  imports: [DatePipe, ReactiveFormsModule, RouterLink],
  templateUrl: './comunicacion-editor.html',
  styleUrls: ['./communication-shared.css', './comunicacion-editor.css'],
})
export class ComunicacionEditor implements OnInit {
  private readonly service = inject(CommunicationsService);
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly audienceRefresh = new Subject<void>();
  private audienceKey = '';
  private savedPayload = '';
  private previewVersion = 0;
  private validScope = false;
  private readonly remoteSearches: Record<RemoteSource, Subject<string>> = {
    usuarios: new Subject<string>(), reservas: new Subject<string>(), salidas: new Subject<string>(), promociones: new Subject<string>(),
  };
  private readonly userNames = new Map<number, string>();
  private readonly relatedNames = { reservas: new Map<number, string>(), salidas: new Map<number, string>(), promociones: new Map<number, string>() };

  protected readonly isGlobal = this.auth.session()?.user.roles.includes('SUPER_ADMIN') ?? false;
  protected readonly showCompanies = signal(false);
  protected readonly audienceLoading = signal(false);
  protected readonly audienceNote = signal<string | null>(null);
  protected readonly emailHtml = signal<SafeHtml | null>(null);
  protected readonly emailLoading = signal(false);
  protected readonly emailError = signal<string | null>(null);
  protected readonly templates = [
    { id: 'viaje', label: 'Preparar el viaje', description: 'Una bienvenida con la información a mano.', type: 'OPERATIVA' as CommunicationType, group: 'CLIENTES' as AudienceGroup,
      title: 'Tu próxima experiencia está cerca', message: 'Hola, {{nombre}}.\n\n¡Nos alegra acompañarte en tu próxima aventura! Antes de salir, revisa el horario y el punto de encuentro en los detalles de tu reserva.\n\nGracias por elegir {{empresa}}. ¡Te esperamos!' },
    { id: 'cambio', label: 'Comunicar un cambio', description: 'Información clara antes de la salida.', type: 'OPERATIVA' as CommunicationType, group: 'CLIENTES' as AudienceGroup,
      title: 'Información importante para tu viaje', message: 'Hola, {{nombre}}.\n\nQueremos que organices tu experiencia con tranquilidad. Te compartimos una actualización sobre tu actividad.\n\nRevisa los detalles de tu reserva antes de salir y conserva este aviso.\n\nEl equipo de {{empresa}}.' },
    { id: 'equipo', label: 'Coordinar al equipo', description: 'Guías y personal, en la misma página.', type: 'INTERNA' as CommunicationType, group: 'PERSONAL' as AudienceGroup,
      title: 'Coordinemos una gran experiencia', message: 'Hola, {{nombre}}.\n\nCompartimos este aviso para preparar nuestro servicio y acompañar mejor a los viajeros. Revisa la organización y los detalles de tu próxima actividad.\n\nGracias por tu compromiso.\n{{empresa}}' },
    { id: 'oferta', label: 'Inspirar una escapada', description: 'Una propuesta para quienes aceptan ofertas.', type: 'PROMOCIONAL' as CommunicationType, group: 'CLIENTES' as AudienceGroup,
      title: 'Tu próxima escapada te espera', message: 'Hola, {{nombre}}.\n\nDescubre una nueva forma de disfrutar Bolivia con {{empresa}}. Conoce nuestra propuesta y revisa sus condiciones, disponibilidad y vigencia antes de reservar.\n\n¡Nos encantará acompañarte en tu próxima experiencia!' },
  ];
  protected readonly tenantId = signal<number | undefined>(undefined);
  protected readonly ready = signal(false);
  protected readonly loading = signal(true);
  protected readonly working = signal(false);
  protected readonly current = signal<Communication | null>(null);
  protected readonly options = signal<CommunicationOptions | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly success = signal<string | null>(null);
  protected readonly changed = signal(true);
  protected readonly preview = signal<AudiencePreview | null>(null);
  protected readonly confirming = signal(false);
  protected readonly conflict = signal(false);
  protected readonly searching = signal<Record<RemoteSource, boolean>>({ usuarios: false, reservas: false, salidas: false, promociones: false });
  protected readonly searchErrors = signal<Record<RemoteSource, string | null>>({ usuarios: null, reservas: null, salidas: null, promociones: null });
  protected readonly linkedSelectors = [
    { source: 'reservas', control: 'reserva_id', label: 'Reserva vinculada', placeholder: 'Sin reserva vinculada' },
    { source: 'salidas', control: 'salida_id', label: 'Salida vinculada', placeholder: 'Sin salida vinculada' },
  ] as const;
  protected readonly senderName = senderName;
  protected readonly searches = signal<Record<Selector, string>>({ empresa_ids: '', rol_ids: '', usuario_ids: '' });
  protected readonly selectors: { key: Selector; label: string; source: 'empresas' | 'roles' | 'usuarios' }[] = [
    { key: 'empresa_ids', label: 'Empresas destinatarias', source: 'empresas' },
    { key: 'rol_ids', label: 'Roles', source: 'roles' },
    { key: 'usuario_ids', label: 'Usuarios', source: 'usuarios' },
  ];
  protected readonly form = this.fb.group({
    titulo: this.fb.nonNullable.control('', [Validators.required, Validators.pattern(/\S/), Validators.maxLength(150)]),
    mensaje: this.fb.nonNullable.control('', [Validators.required, Validators.pattern(/\S/), Validators.maxLength(10000)]),
    tipo: this.fb.nonNullable.control<CommunicationType>('INTERNA', Validators.required),
    grupo: this.fb.nonNullable.control<AudienceGroup>('PERSONAL', Validators.required),
    empresa_ids: this.fb.nonNullable.control<number[]>([]),
    rol_ids: this.fb.nonNullable.control<number[]>([]),
    usuario_ids: this.fb.nonNullable.control<number[]>([]),
    reserva_id: this.fb.control<number | null>(null, [Validators.min(1), Validators.pattern(/^\d+$/)]),
    salida_id: this.fb.control<number | null>(null, [Validators.min(1), Validators.pattern(/^\d+$/)]),
    promocion_id: this.fb.control<number | null>(null),
    programado_en: this.fb.nonNullable.control(''),
    vence_en: this.fb.nonNullable.control(''),
  });

  ngOnInit(): void {
    for (const source of ['usuarios', 'reservas', 'salidas', 'promociones'] as const) this.watchSearch(source);
    this.audienceRefresh.pipe(debounceTime(150), switchMap(() => {
      const filters = this.optionFilters();
      const key = JSON.stringify(filters);
      return this.service.options(this.tenantId(), '', filters).pipe(
        map((options) => JSON.stringify(this.optionFilters()) === key ? options : null),
        catchError(() => { this.audienceNote.set('No se pudieron actualizar las opciones. Vuelve a cambiar la audiencia para reintentar.'); return of(null); }));
    }),
      takeUntilDestroyed(this.destroyRef)).subscribe((options) => {
        if (options) { this.options.set(options); this.rememberOptions(options); }
        this.audienceLoading.set(false);
      });
    this.form.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
      const { tipo, grupo } = this.form.getRawValue();
      if (tipo === 'INTERNA' && (grupo === 'CLIENTES' || grupo === 'TODOS')) {
        this.form.controls.grupo.setValue('PERSONAL', { emitEvent: false });
      }
      const selected = this.form.getRawValue();
      const validRoles = selected.rol_ids.filter((id) => {
        const role = this.options()?.roles.find((option) => option.id === id);
        return !selected.empresa_ids.length || !role?.ambito || role.ambito === 'TENANT' && (!role.empresa_id || selected.empresa_ids.includes(role.empresa_id));
      });
      if (validRoles.length !== selected.rol_ids.length) {
        this.form.controls.rol_ids.setValue(validRoles, { emitEvent: false });
        this.audienceNote.set('Actualizamos los roles para que correspondan a las empresas elegidas. Revisa la audiencia antes de enviar.');
      }
      const key = JSON.stringify(this.optionFilters());
      if (this.audienceKey && this.audienceKey !== key) {
        if (this.form.controls.usuario_ids.value.length) {
          this.form.controls.usuario_ids.setValue([], { emitEvent: false });
          this.audienceNote.set('La audiencia cambió. Vuelve a elegir las personas concretas, si necesitas limitar el envío.');
        }
        this.refreshAudienceOptions();
      }
      this.audienceKey = key;
      this.emailHtml.set(null);
      this.changed.set(JSON.stringify(this.payload()) !== this.savedPayload || this.companySelectionMissing());
      this.invalidatePreview();
      this.success.set(null);
    });
    try {
      this.tenantId.set(communicationScope(this.auth.session()?.user, this.route.snapshot.queryParamMap.get('empresa')));
      this.validScope = true;
    } catch (error) {
      this.error.set((error as Error).message);
      this.loading.set(false);
      return;
    }
    this.load();
  }

  private watchSearch(source: RemoteSource): void {
    this.remoteSearches[source].pipe(
      debounceTime(300),
      switchMap((query) => {
        this.searching.update((state) => ({ ...state, [source]: true }));
        this.searchErrors.update((state) => ({ ...state, [source]: null }));
        const filters = this.optionFilters();
        const key = JSON.stringify(filters);
        return this.service.options(this.tenantId(), query, filters).pipe(
          map((options) => JSON.stringify(this.optionFilters()) === key ? options : null),
          catchError((error: HttpErrorResponse) => {
          this.searchErrors.update((state) => ({ ...state, [source]: apiErrorMessage(error, 'No se pudieron cargar las opciones.') }));
            return of(null);
          }));
      }),
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((options) => {
      if (options) {
        this.rememberOptions(options);
        this.options.update((current) => current ? { ...current, [source]: options[source] ?? [] } : current);
      }
      this.searching.update((state) => ({ ...state, [source]: false }));
    });
  }

  protected load(): void {
    if (!this.validScope || this.working()) return;
    const rawId = this.route.snapshot.paramMap.get('id');
    const id = rawId === null ? null : Number(rawId);
    if (id !== null && (!Number.isSafeInteger(id) || id <= 0)) {
      this.error.set('La comunicación solicitada no es válida.');
      this.loading.set(false);
      return;
    }
    this.loading.set(true);
    this.ready.set(false);
    this.error.set(null);
    this.invalidatePreview();
    forkJoin({
      options: this.service.options(this.tenantId()),
      item: id === null ? of(null) : this.service.detail(id, this.tenantId()),
    }).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: ({ options, item }) => {
        this.options.set(options);
        this.rememberOptions(options);
        if (item) this.apply(item);
        this.ready.set(true);
        this.loading.set(false);
        this.audienceKey = JSON.stringify(this.optionFilters());
        this.refreshAudienceOptions();
      },
      error: (error: HttpErrorResponse) => {
        this.error.set(apiErrorMessage(error, 'No se pudo abrir la comunicación.'));
        this.loading.set(false);
      },
    });
  }

  private apply(item: Communication): void {
    this.conflict.set(false);
    this.current.set(item);
    this.form.reset({
      titulo: item.titulo, mensaje: item.mensaje, tipo: item.tipo, grupo: item.audiencia.grupo,
      empresa_ids: item.audiencia.empresa_ids ?? [], rol_ids: item.audiencia.rol_ids ?? [], usuario_ids: item.audiencia.usuario_ids ?? [],
      reserva_id: item.reserva_id ?? item.audiencia.reserva_id ?? null, salida_id: item.audiencia.salida_id ?? null,
      promocion_id: item.promocion_id ?? null, programado_en: this.localDate(item.programado_en), vence_en: this.localDate(item.vence_en),
    }, { emitEvent: false });
    this.audienceKey = JSON.stringify(this.optionFilters());
    this.showCompanies.set(!!item.audiencia.empresa_ids?.length);
    this.savedPayload = JSON.stringify(this.payload());
    this.changed.set(false);
    this.invalidatePreview();
  }

  protected payload(): CommunicationPayload {
    const value = this.form.getRawValue();
    return {
      titulo: value.titulo.trim(), mensaje: value.mensaje.trim(), tipo: value.tipo,
      audiencia: {
        grupo: value.grupo, empresa_ids: value.empresa_ids, rol_ids: value.rol_ids, usuario_ids: value.usuario_ids,
        ...(value.reserva_id ? { reserva_id: value.reserva_id } : {}),
        ...(value.salida_id ? { salida_id: value.salida_id } : {}),
      },
      reserva_id: value.reserva_id ?? null,
      programado_en: value.programado_en ? new Date(value.programado_en).toISOString() : null,
      vence_en: value.vence_en ? new Date(value.vence_en).toISOString() : null,
      promocion_id: value.tipo === 'PROMOCIONAL' ? value.promocion_id : null,
    };
  }

  protected save(): void {
    if (!this.ready() || this.working() || (this.current() !== null && this.current()?.estado !== 'BORRADOR')) return;
    if (this.isGlobal && this.showCompanies() && !this.form.controls.empresa_ids.value.length) { this.error.set('Selecciona al menos una empresa o elige toda la plataforma.'); return; }
    this.form.markAllAsTouched();
    if (this.form.invalid) { this.error.set('Completa título y mensaje y revisa la reserva y salida seleccionadas.'); return; }
    if (this.form.controls.grupo.value === 'USUARIOS' && !this.form.controls.usuario_ids.value.length) {
      this.error.set('Selecciona al menos un usuario para este grupo.'); return;
    }
    this.working.set(true);
    this.error.set(null);
    this.invalidatePreview();
    const item = this.current();
    const request = item
      ? this.service.update(item.id, this.payload(), this.tenantId())
      : this.service.create(this.payload(), this.tenantId());
    request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (saved) => {
        this.apply(saved);
        this.working.set(false);
        this.success.set('Borrador guardado. Ya puedes previsualizar sus destinatarios.');
        if (!item) void this.router.navigate(['/comunicaciones', saved.id], {
          queryParams: { empresa: this.tenantId() }, replaceUrl: true,
        });
      },
      error: (error: HttpErrorResponse) => this.fail(error, 'No se pudo guardar el borrador.'),
    });
  }

  protected previewAudience(): void {
    if (!this.ready() || !this.current() || this.changed() || this.companySelectionMissing() || this.working() || this.conflict() || this.current()?.estado !== 'BORRADOR') return;
    this.invalidatePreview();
    const version = this.previewVersion;
    this.working.set(true);
    this.error.set(null);
    this.service.preview(this.payload(), this.tenantId()).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (preview) => {
        if (version === this.previewVersion) {
          this.preview.set(preview);
          this.revealStep('#audience-title');
        }
        this.working.set(false);
      },
      error: (error: HttpErrorResponse) => this.fail(error, 'No se pudo previsualizar la audiencia.'),
    });
  }

  protected preparePublish(): void {
    const preview = this.preview();
    if (!this.changed() && !this.working() && preview?.huella && preview.total > 0 && this.current()?.estado === 'BORRADOR') {
      this.confirming.set(true);
      this.revealStep('#publish-title');
    }
  }

  protected cancelPublish(): void {
    if (this.working()) return;
    this.confirming.set(false);
    this.revealStep('#audience-title');
  }

  private revealStep(selector: string): void {
    afterNextRender(() => {
      const heading = this.host.nativeElement.querySelector<HTMLElement>(selector);
      heading?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      heading?.focus({ preventScroll: true });
    }, { injector: this.injector });
  }

  protected publish(): void {
    const item = this.current();
    const preview = this.preview();
    if (!this.confirming() || !item || item.estado !== 'BORRADOR' || !preview?.huella || preview.total <= 0 || this.changed() || this.working()) return;
    this.working.set(true);
    this.error.set(null);
    this.service.publish(item.id, preview.huella, this.tenantId()).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (published) => {
        this.apply(published);
        this.working.set(false);
        this.success.set(published.estado === 'PROGRAMADA' ? 'Envío programado. Puedes cancelarlo antes de su despacho.' : 'Comunicación publicada. Consulta aquí sus lecturas y envíos.');
      },
      error: (error: HttpErrorResponse) => {
        this.invalidatePreview();
        this.fail(error, 'No se pudo publicar la comunicación.');
        if (error.status === 409) {
          this.conflict.set(true);
          this.error.set('La comunicación o sus destinatarios cambiaron. Recarga el borrador y vuelve a previsualizar antes de publicar.');
        }
      },
    });
  }

  protected groups(): typeof GROUPS {
    return this.form.controls.tipo.value === 'INTERNA' ? GROUPS.filter((group) => !['TODOS', 'CLIENTES'].includes(group.value)) : GROUPS;
  }

  protected scopeLabel(): string {
    const id = this.tenantId();
    return id === undefined ? 'Toda la plataforma (global)' : this.options()?.empresas.find((company) => company.id === id)?.nombre
      ?? this.auth.session()?.user.tenants.find((company) => company.id === id)?.name ?? `Empresa #${id}`;
  }

  protected search(key: Selector, event: Event): void {
    const query = (event.target as HTMLInputElement).value;
    this.searches.update((values) => ({ ...values, [key]: query }));
    if (key === 'usuario_ids') this.remoteSearches.usuarios.next(query);
  }

  protected searchRelated(source: 'reservas' | 'salidas' | 'promociones', event: Event): void {
    this.remoteSearches[source].next((event.target as HTMLInputElement).value);
  }

  protected relatedOptions(source: 'reservas' | 'salidas' | 'promociones', id: number | null): CommunicationOption[] {
    const options = this.options()?.[source] ?? [];
    return id && !options.some((option) => option.id === id)
      ? [{ id, nombre: this.relatedNames[source].get(id) ?? (source === 'reservas' ? 'Reserva vinculada (fuera de los resultados actuales)' : 'Salida vinculada (fuera de los resultados actuales)') }, ...options]
      : options;
  }

  protected choices(source: 'empresas' | 'roles' | 'usuarios', key: Selector): (CommunicationOption & { email?: string })[] {
    const query = this.searches()[key].trim().toLocaleLowerCase('es');
    return (this.options()?.[source] ?? []).filter((item) => source !== 'roles' || !this.form.controls.empresa_ids.value.length || !item.ambito || item.ambito === 'TENANT' && (!item.empresa_id || this.form.controls.empresa_ids.value.includes(item.empresa_id))).filter((item) => `${item.nombre} ${'email' in item ? item.email : ''}`.toLocaleLowerCase('es').includes(query));
  }

  protected toggle(key: Selector, id: number): void {
    if (this.working() || (this.current() !== null && this.current()?.estado !== 'BORRADOR')) return;
    const control = this.form.controls[key];
    control.setValue(control.value.includes(id) ? control.value.filter((value) => value !== id) : [...control.value, id]);
  }

  protected selectedLabels(source: 'empresas' | 'roles' | 'usuarios', key: Selector): string {
    return this.form.controls[key].value.map((id) => this.optionLabel(source, id)).join(', ');
  }

  protected optionLabel(source: 'empresas' | 'roles' | 'usuarios', id: number): string {
    return (source === 'usuarios' ? this.userNames.get(id) : this.options()?.[source].find((item) => item.id === id)?.nombre) ?? `#${id}`;
  }

  private rememberOptions(options: CommunicationOptions): void {
    options.usuarios.forEach((user) => this.userNames.set(user.id, `${user.nombre} (${user.email})`));
    for (const source of ['reservas', 'salidas', 'promociones'] as const) {
      (options[source] ?? []).forEach((option) => this.relatedNames[source].set(option.id, option.nombre));
    }
  }

  private optionFilters() {
    const form = this.form.getRawValue();
    return { empresa_ids: form.empresa_ids, rol_ids: form.rol_ids, grupo: form.grupo, tipo: form.tipo };
  }

  private refreshAudienceOptions(): void {
    if (!this.validScope) return;
    this.audienceLoading.set(true);
    this.audienceRefresh.next();
  }

  protected setCompanyMode(selected: boolean): void {
    this.showCompanies.set(selected);
    if (!selected) this.form.controls.empresa_ids.setValue([]);
    else {
      this.changed.set(true);
      this.invalidatePreview();
    }
  }

  private companySelectionMissing(): boolean {
    return this.isGlobal && this.showCompanies() && !this.form.controls.empresa_ids.value.length;
  }

  protected useTemplate(id: string): void {
    if (this.current() && this.current()?.estado !== 'BORRADOR') return;
    const template = this.templates.find((item) => item.id === id);
    if (template) this.form.patchValue({ titulo: template.title, mensaje: template.message, tipo: template.type, grupo: template.group });
  }

  protected insertVariable(name: 'nombre' | 'empresa'): void {
    const textarea = this.host.nativeElement.querySelector<HTMLTextAreaElement>('#message-body');
    const value = this.form.controls.mensaje.value;
    const start = textarea?.selectionStart ?? value.length;
    const end = textarea?.selectionEnd ?? start;
    const token = '{{' + name + '}}';
    this.form.controls.mensaje.setValue(value.slice(0, start) + token + value.slice(end));
    afterNextRender(() => { textarea?.focus(); textarea?.setSelectionRange(start + token.length, start + token.length); }, { injector: this.injector });
  }

  protected visualMessage(text: string): string {
    return text.replaceAll('{{nombre}}', 'María').replaceAll('{{empresa}}', this.current() ? senderName(this.current()?.remitente) : this.isGlobal && this.tenantId() === undefined ? 'SITUR-SMART' : this.options()?.empresas.find((item) => item.id === this.tenantId())?.nombre ?? 'Tu empresa');
  }

  protected previewEmail(): void {
    const item = this.current();
    if (!item || this.changed() || this.emailLoading()) return;
    const version = this.previewVersion;
    this.emailLoading.set(true); this.emailError.set(null);
    this.service.emailPreview(item.id, this.tenantId()).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (content) => { if (version === this.previewVersion) this.emailHtml.set(this.sanitizer.bypassSecurityTrustHtml(content.html)); this.emailLoading.set(false); },
      error: () => { this.emailLoading.set(false); this.emailError.set('No pudimos cargar el correo. Puedes reintentarlo.'); },
    });
  }

  private localDate(value?: string | null): string {
    if (!value) return '';
    const date = new Date(value);
    const pad = (number: number) => String(number).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  protected cancelSchedule(): void {
    const item = this.current();
    if (!item || this.working() || !['PROGRAMADA', 'REVISION'].includes(item.estado)) return;
    this.working.set(true);
    this.service.cancel(item.id, this.tenantId()).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (cancelled) => { this.apply(cancelled); this.working.set(false); this.success.set('Envío cancelado.'); },
      error: (error: HttpErrorResponse) => this.fail(error, 'No se pudo cancelar el envío.'),
    });
  }

  private invalidatePreview(): void {
    this.previewVersion++;
    this.preview.set(null);
    this.confirming.set(false);
  }

  private fail(error: HttpErrorResponse, fallback: string): void {
    this.working.set(false);
    this.error.set(apiErrorMessage(error, fallback));
  }
}
