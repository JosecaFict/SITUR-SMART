import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, input, output, signal } from '@angular/core';
import { AccountService } from '../../core/auth/account.service';
import { apiErrorMessage } from '../../core/http/api-error';

/**
 * Pide el código de 6 dígitos para verificar el correo. Sin correo verificado
 * el turista no puede reservar; lo usan Mi perfil y el formulario de reserva.
 */
@Component({
  selector: 'situr-verificar-correo',
  template: `
    <div class="rounded-xl border border-amber-200 bg-amber-50 p-4">
      <p class="text-sm font-semibold text-amber-900">Verifica tu correo</p>
      <p class="mt-1 text-xs leading-5 text-amber-800">
        Para reservar necesitamos confirmar tu correo. Escribe el código de 6 dígitos que te enviamos.
      </p>
      <form class="mt-3 flex flex-wrap gap-2" (submit)="$event.preventDefault(); confirm()">
        <input class="field-control w-36 text-center font-mono text-lg tracking-[0.3em]" inputmode="numeric" maxlength="6"
          [value]="code()" (input)="code.set($any($event.target).value)" aria-label="Código de verificación" />
        <button type="submit" class="primary-button" [disabled]="working()">Verificar</button>
        <button type="button" class="secondary-button" [disabled]="working()" (click)="resend()">Reenviar código</button>
      </form>
      @if (info(); as text) { <p class="mt-2 text-xs text-amber-900">{{ text }}</p> }
      @if (error(); as text) { <p class="mt-2 text-xs font-semibold text-red-700">{{ text }}</p> }
    </div>
  `,
})
export class VerificarCorreo implements OnInit {
  private readonly account = inject(AccountService);

  /** Manda un código nuevo al mostrarse. */
  readonly sendFirst = input(false);
  readonly verified = output<void>();

  protected readonly code = signal('');
  protected readonly working = signal(false);
  protected readonly info = signal<string | null>(null);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    if (this.sendFirst()) this.resend();
  }

  protected resend(): void {
    this.error.set(null);
    this.account.sendEmailCode().subscribe({
      next: () => this.info.set('Te enviamos un código nuevo. Revisa tu correo (y la carpeta de spam).'),
      error: (error: HttpErrorResponse) => this.error.set(apiErrorMessage(error, 'No se pudo enviar el código.')),
    });
  }

  protected confirm(): void {
    if (this.code().trim().length !== 6) {
      this.error.set('El código tiene 6 dígitos.');
      return;
    }
    this.working.set(true);
    this.error.set(null);
    this.account.confirmEmail(this.code()).subscribe({
      next: () => {
        this.working.set(false);
        this.verified.emit();
      },
      error: (error: HttpErrorResponse) => {
        this.working.set(false);
        this.error.set(apiErrorMessage(error, 'No se pudo verificar el código.'));
      },
    });
  }
}
