import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { environment } from '../../../environments/environment';
import { AsistenteChat } from './asistente-chat';

describe('AsistenteChat', () => {
  let fixture: ComponentFixture<AsistenteChat>;
  let http: HttpTestingController;
  const autenticado = signal(true);
  const base = `${environment.apiUrl}/asistente`;
  const el = () => fixture.nativeElement as HTMLElement;

  function montar(estado = { chat: true, voz: true }) {
    fixture = TestBed.createComponent(AsistenteChat);
    http = TestBed.inject(HttpTestingController);
    http.expectOne(`${base}/estado/`).flush(estado);
    fixture.detectChanges();
  }

  function abrir() {
    el().querySelector<HTMLButtonElement>('button[aria-label="Abrir asistente virtual"]')!.click();
    fixture.detectChanges();
  }

  beforeEach(async () => {
    autenticado.set(true);
    await TestBed.configureTestingModule({
      imports: [AsistenteChat],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: { isAuthenticated: autenticado } },
      ],
    }).compileComponents();
  });

  afterEach(() => http.verify());

  it('no se muestra si el backend no tiene IA configurada', () => {
    montar({ chat: false, voz: false });
    expect(el().querySelector('button')).toBeNull();
  });

  it('no se muestra sin sesión', () => {
    autenticado.set(false);
    montar();
    expect(el().querySelector('button')).toBeNull();
  });

  it('envía el mensaje y muestra la respuesta con tarjetas de hospedaje', () => {
    montar();
    abrir();

    el().querySelector<HTMLButtonElement>('section button.rounded-full')!.click();
    const req = http.expectOne(`${base}/chat/`);
    expect(req.request.body.mensaje).toBe('Hotel en Uyuni para 2 personas');
    expect(req.request.body.historial).toEqual([]);
    req.flush({
      respuesta: 'Te recomiendo **Hotel Sal**.',
      hospedajes: [
        {
          id: 3, nombre: 'Hotel Sal', tipo: 'Hotel', ciudad: 'Uyuni', localidad: null,
          empresa: 'X', estrellas: 3, precio_desde: '250.00', moneda: 'Bs', servicios: [],
          imagen_url: null, url: '/marketplace/hospedajes/3',
        },
      ],
    });
    fixture.detectChanges();

    expect(el().textContent).toContain('Te recomiendo Hotel Sal.');
    const tarjeta = el().querySelector<HTMLAnchorElement>('a[href="/marketplace/hospedajes/3"]');
    expect(tarjeta?.textContent).toContain('Desde Bs 250.00');
  });

  it('muestra el error del backend sin romper el chat', () => {
    montar();
    abrir();

    el().querySelector<HTMLButtonElement>('section button.rounded-full')!.click();
    http
      .expectOne(`${base}/chat/`)
      .flush({ message: 'El asistente alcanzó su límite de uso.' }, { status: 503, statusText: 'x' });
    fixture.detectChanges();

    expect(el().querySelector('.bg-red-50')).not.toBeNull();
  });

  it('oculta el micrófono si el backend no tiene modelo de voz', () => {
    montar({ chat: true, voz: false });
    abrir();
    expect(el().querySelector('button[aria-label="Hablar con el asistente"]')).toBeNull();
  });
});
