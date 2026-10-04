import { HttpHeaders, HttpResponse } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { BackupsService } from '../../../core/backups/backups.service';
import { CopiasSeguridad } from './copias-seguridad';

describe('CopiasSeguridad', () => {
  let fixture: ComponentFixture<CopiasSeguridad>;
  const backups = jasmine.createSpyObj<BackupsService>('BackupsService', ['download']);

  beforeEach(async () => {
    backups.download.calls.reset();
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
    spyOn(URL, 'createObjectURL').and.returnValue('blob:test');
    spyOn(URL, 'revokeObjectURL');
    spyOn(HTMLAnchorElement.prototype, 'click');
    await TestBed.configureTestingModule({
      imports: [CopiasSeguridad],
      providers: [{ provide: BackupsService, useValue: backups }],
    }).compileComponents();
    fixture = TestBed.createComponent(CopiasSeguridad);
    fixture.detectChanges();
  });

  it('asks for confirmation before generating the dump', () => {
    const firstButton = fixture.nativeElement.querySelector('button') as HTMLButtonElement;
    firstButton.click();
    fixture.detectChanges();
    expect(backups.download).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('¿Generar y descargar la copia ahora?');
  });
});
