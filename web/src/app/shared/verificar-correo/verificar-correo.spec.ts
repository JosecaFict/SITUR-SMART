import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { HttpErrorResponse } from '@angular/common/http';
import { AccountService } from '../../core/auth/account.service';
import { AuthUser } from '../../core/auth/auth.models';
import { VerificarCorreo } from './verificar-correo';

describe('VerificarCorreo', () => {
  let fixture: ComponentFixture<VerificarCorreo>;
  let account: jasmine.SpyObj<AccountService>;

  beforeEach(async () => {
    account = jasmine.createSpyObj<AccountService>('AccountService', ['sendEmailCode', 'confirmEmail']);
    account.sendEmailCode.and.returnValue(of(undefined));
    await TestBed.configureTestingModule({
      imports: [VerificarCorreo],
      providers: [{ provide: AccountService, useValue: account }],
    }).compileComponents();
    fixture = TestBed.createComponent(VerificarCorreo);
    fixture.detectChanges();
  });

  function enter(code: string): void {
    const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
    input.value = code;
    input.dispatchEvent(new Event('input'));
    (fixture.nativeElement.querySelector('button[type="submit"]') as HTMLButtonElement).click();
    fixture.detectChanges();
  }

  it('avisa si el código está incompleto o es incorrecto', () => {
    enter('12');
    expect(account.confirmEmail).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('6 dígitos');

    account.confirmEmail.and.returnValue(throwError(() => new HttpErrorResponse({
      status: 400, error: { error: { message: 'El código no es correcto.' } },
    })));
    enter('000000');
    expect(fixture.nativeElement.textContent).toContain('El código no es correcto.');
  });

  it('con el código correcto avisa que quedó verificado', () => {
    let verified = false;
    fixture.componentInstance.verified.subscribe(() => (verified = true));
    account.confirmEmail.and.returnValue(of({ correo_verificado: true } as AuthUser));
    enter('123456');
    expect(account.confirmEmail).toHaveBeenCalledWith('123456');
    expect(verified).toBeTrue();
  });
});
