import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { environment } from '../../../../environments/environment';
import { DashboardStats } from '../../../core/dashboard/dashboard-stats.models';
import { PanelNegocio } from './panel-negocio';

const url = `${environment.apiUrl}/dashboard/`;
const serie = ['Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov'].map((etiqueta, i) => ({
  mes: `2026-${String(i + 6).padStart(2, '0')}`, etiqueta, cobrado: `${(i + 1) * 1000}.00`,
  reembolsado: '100.00', neto: `${(i + 1) * 1000 - 100}.00`, reservas: i + 2,
}));

function stats(extra: Partial<DashboardStats> = {}): DashboardStats {
  return {
    alcance: 'empresa', empresas: [5], generado: '2026-11-25T10:00:00-04:00', mes: 'Nov 2026',
    finanzas: { moneda: 'BOB', cobrado: '24120.00', reembolsado: '1280.00', neto: '22840.00', variacion_neto: 11.2, serie },
    reservas: {
      total: 52, variacion: -4, canceladas: 4,
      por_estado: [{ estado: 'CONFIRMADA', etiqueta: 'Confirmadas', total: 41, porcentaje: 78.8 }],
    },
    ocupacion: { vendidos: 78, capacidad: 100, porcentaje: 78 },
    calificacion: {
      promedio: 4.5, total: 87, nuevas_mes: 9,
      ultimas: [{ autor: 'Lucía R.', calificacion: 5, comentario: 'Excelente ubicación', producto: 'Suite', fecha: '2026-11-20' }],
    },
    alertas: [{ clave: 'pagos_revision', titulo: 'Pagos en revisión', detalle: 'x', nivel: 'media', total: 2, ruta: '/pagos' }],
    productos_top: [{ id: 1, nombre: 'Doble superior', ciudad: 'Santa Cruz', reservas: 18, unidades: 20, ingreso: '8640.00' }],
    catalogo: { publicados: 10, total: 12 },
    proximas: [{
      reserva: 'R1', inicio: '2026-11-26T15:00:00-04:00', cliente: 'María Quispe', producto: 'Doble superior',
      cantidad: 1, dias: 3, monto: '960.00', estado: 'CONFIRMADA',
    }],
    promociones: [{
      id: 1, nombre: 'Fin de semana cruceño', porcentaje: '15', usos: 23,
      inicia: '2026-11-01T00:00:00-04:00', vence: '2026-11-30T23:59:00-04:00', vigente: true,
    }],
    ...extra,
  };
}

describe('PanelNegocio', () => {
  let fixture: ComponentFixture<PanelNegocio>;
  let http: HttpTestingController;
  const el = () => fixture.nativeElement as HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PanelNegocio],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(PanelNegocio);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('la empresa pide sus indicadores con su X-Tenant-ID y los muestra', () => {
    fixture.componentRef.setInput('tenantId', 5);
    fixture.detectChanges();

    const req = http.expectOne((r) => r.url === url);
    expect(req.request.headers.get('X-Tenant-ID')).toBe('5');
    expect(req.request.params.has('empresas')).toBeFalse();
    req.flush(stats());
    fixture.detectChanges();

    const text = el().textContent ?? '';
    expect(el().querySelector('[data-testid="kpi-dinero"]')?.textContent).toContain('22.840,00');
    expect(text).toContain('Ocupación del mes');
    expect(text).toContain('Pagos en revisión');
    expect(text).toContain('María Quispe');
    expect(text).toContain('26 nov');
    expect(text).toContain('Lucía R.');
    expect(text).toContain('Fin de semana cruceño');
    expect(text).not.toContain('Ranking de empresas');
  });

  it('avisa si el rol no tiene permiso de ver ventas', () => {
    fixture.componentRef.setInput('tenantId', 5);
    fixture.detectChanges();
    http.expectOne((r) => r.url === url).flush({ detail: 'x' }, { status: 403, statusText: 'Forbidden' });
    fixture.detectChanges();
    expect(el().textContent).toContain('no tiene permiso');
  });

  describe('SuperAdmin', () => {
    const platform = (extra: Partial<DashboardStats> = {}) => stats({
      alcance: 'plataforma', empresas: [], proximas: undefined, promociones: undefined,
      plataforma: {
        empresas: { total: 18, activas: 17, tasa_activacion: 94.4 },
        turistas: { total: 1284, nuevos_mes: 126, con_compra: 745, porcentaje_compra: 58 },
      },
      ranking: [{ id: 3, nombre: 'Hotel Cortez', cobrado: '24120.00', reservas: 52, calificacion: 4.5 }],
      suscripciones: [{ plan: 'Profesional', empresas: 9 }],
      ciudades: [{ ciudad: 'Uyuni', reservas: 118 }],
      ultimas_reservas: [],
      comparacion: [],
      ...extra,
    });

    beforeEach(() => {
      fixture.componentRef.setInput('platform', true);
      fixture.componentRef.setInput('companies', [
        { id: 3, name: 'Hotel Cortez' }, { id: 7, name: 'Gravity Bolivia' }, { id: 9, name: 'SczTourBo' },
      ]);
      fixture.detectChanges();
    });

    it('ve la plataforma sin X-Tenant-ID', () => {
      const req = http.expectOne((r) => r.url === url);
      expect(req.request.headers.has('X-Tenant-ID')).toBeFalse();
      req.flush(platform());
      fixture.detectChanges();

      const text = el().textContent ?? '';
      expect(text).toContain('Turistas registrados');
      expect(text).toContain('Ranking de empresas');
      expect(text).toContain('Uyuni');
      expect(el().querySelector('[data-testid="tabla-comparacion"]')).toBeNull();
    });

    it('elige dos empresas y las compara lado a lado', () => {
      http.expectOne((r) => r.url === url).flush(platform());
      fixture.detectChanges();

      el().querySelector<HTMLButtonElement>('[data-testid="empresas-picker"]')!.click();
      fixture.detectChanges();
      const boxes = el().querySelectorAll<HTMLInputElement>('input[type="checkbox"]');
      boxes[0].click();
      http.expectOne((r) => r.url === url && r.params.get('empresas') === '3').flush(platform({ empresas: [3] }));
      boxes[1].click();
      const req = http.expectOne((r) => r.url === url && r.params.get('empresas') === '3,7');
      const row = (id: number, nombre: string, neto: string) => ({
        id, nombre, cobrado: neto, reembolsado: '0.00', neto, reservas: 4, canceladas: 1, ocupacion: 50,
        calificacion: 4.2, serie: serie.map((m) => ({ etiqueta: m.etiqueta, neto: m.neto })),
      });
      req.flush(platform({ empresas: [3, 7], comparacion: [row(3, 'Hotel Cortez', '900.00'), row(7, 'Gravity Bolivia', '1200.00')] }));
      fixture.detectChanges();

      const table = el().querySelector('[data-testid="tabla-comparacion"]');
      expect(table?.textContent).toContain('Hotel Cortez');
      expect(table?.textContent).toContain('Gravity Bolivia');
      expect(el().textContent).toContain('Comparación de empresas');
    });
  });
});
