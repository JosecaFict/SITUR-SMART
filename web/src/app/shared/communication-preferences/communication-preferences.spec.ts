import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Subject, of } from 'rxjs';
import { CommunicationsService } from '../../core/communications/communications.service';
import { CommunicationPreferences as Preferences } from '../../core/communications/communications.models';
import { CommunicationPreferences } from './communication-preferences';

describe('Preferencias de promociones', () => {
  let fixture: ComponentFixture<CommunicationPreferences>;
  let service: jasmine.SpyObj<CommunicationsService>;
  const initial: Preferences = { preferencias: [{ empresa_id: 7, nombre: 'Hotel', promociones: false }], limites: { por_empresa_24h: 1, total_24h: 3 } };

  beforeEach(async () => {
    service = jasmine.createSpyObj('CommunicationsService', ['preferences', 'setPreference']);
    service.preferences.and.returnValue(of(initial));
    await TestBed.configureTestingModule({ imports: [CommunicationPreferences], providers: [{ provide: CommunicationsService, useValue: service }] }).compileComponents();
    fixture = TestBed.createComponent(CommunicationPreferences); fixture.detectChanges();
  });

  it('muestra remitente, límites y separación de avisos operativos', () => {
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Hotel'); expect(text).toContain('no afecta'); expect(text).toContain('3 promociones');
  });

  it('solo refleja consentimiento confirmado y bloquea cambios simultáneos', () => {
    const response = new Subject<Preferences>(); service.setPreference.and.returnValue(response);
    const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
    input.checked = true; input.dispatchEvent(new Event('change')); fixture.detectChanges();
    expect(service.setPreference).toHaveBeenCalledOnceWith(7, true);
    expect(input.checked).toBeFalse(); expect(input.disabled).toBeTrue();
    response.next({ ...initial, preferencias: [{ ...initial.preferencias[0], promociones: true }] }); fixture.detectChanges();
    expect(input.checked).toBeTrue(); expect(input.disabled).toBeFalse();
  });

  it('conserva preferencia al fallar y permite reintentar', () => {
    const response = new Subject<Preferences>(); service.setPreference.and.returnValue(response);
    const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
    input.checked = true; input.dispatchEvent(new Event('change')); response.error(new Error('sin red')); fixture.detectChanges();
    expect(input.checked).toBeFalse(); expect(input.disabled).toBeFalse();
    expect(fixture.nativeElement.textContent).toContain('No se pudo guardar');
  });
});
