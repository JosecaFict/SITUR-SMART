import { HttpHeaders, HttpResponse } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { of } from 'rxjs';
import { BackupSchedule, BackupsService, StoredBackup } from '../../../core/backups/backups.service';
import { CopiasSeguridad } from './copias-seguridad';

const SCHEDULE: BackupSchedule = {
  frecuencia: 'SEMANAL',
  ultima_ejecucion: null,
  proxima_ejecucion: '2026-10-07T03:00:00-04:00',
  almacen_configurado: true,
};

const STORED: StoredBackup = {
  id: 4,
  archivo: 'situr-smart-20261006-030000.dump',
  tamano_bytes: 2048,
  sha256: 'a'.repeat(64),
  origen: 'PROGRAMADA',
  creado_en: '2026-10-06T03:00:00-04:00',
};

describe('CopiasSeguridad', () => {
  let fixture: ComponentFixture<CopiasSeguridad>;
  let backups: jasmine.SpyObj<BackupsService>;

  async function render(query: Record<string, string> = {}): Promise<void> {
    backups = jasmine.createSpyObj<BackupsService>('BackupsService', [
      'download', 'schedule', 'updateSchedule', 'stored', 'createStored', 'link',
    ]);
    backups.download.and.returnValue(
      of(
        new HttpResponse({
          body: new Blob(['PGDMP']),
          headers: new HttpHeaders({
            'Content-Disposition': 'attachment; filename="situr-smart-test.dump"',
            'X-Backup-SHA256': 'a'.repeat(64),
          }),
        }),
      ),
    );
    backups.schedule.and.returnValue(of(SCHEDULE));
    backups.updateSchedule.and.callFake((frecuencia) => of({ ...SCHEDULE, frecuencia }));
    backups.stored.and.returnValue(of([STORED]));
    backups.link.and.returnValue(of({ url: 'https://firmado.test/copia' }));
    await TestBed.configureTestingModule({
      imports: [CopiasSeguridad],
      providers: [
        { provide: BackupsService, useValue: backups },
        { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: convertToParamMap(query) } } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(CopiasSeguridad);
    fixture.detectChanges();
  }

  it('asks for confirmation before generating the dump', async () => {
    await render();
    const firstButton = fixture.nativeElement.querySelector('button') as HTMLButtonElement;
    firstButton.click();
    fixture.detectChanges();
    expect(backups.download).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('¿Generar y descargar la copia ahora?');
  });

  it('shows the schedule and the stored copies', async () => {
    await render();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Copia automática');
    expect(text).toContain('Próxima copia');
    expect(text).toContain('/10/2026');
    expect(text).toContain(STORED.archivo);
    expect(text).toContain('Automática');
  });

  it('saves a new frequency', async () => {
    await render();
    const button = Array.from(fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>)
      .find((item) => item.textContent?.trim() === 'Cada 3 días');
    button?.click();
    fixture.detectChanges();
    expect(backups.updateSchedule).toHaveBeenCalledWith('CADA_3_DIAS');
    expect(fixture.nativeElement.textContent).toContain('Programación guardada');
  });

  it('warns when the copy from the email link is gone', async () => {
    await render({ copia: '99' });
    expect(backups.link).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('ya no está disponible');
  });
});
