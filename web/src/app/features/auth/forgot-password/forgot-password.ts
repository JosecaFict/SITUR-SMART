import { Component, OnDestroy, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import {
  LucideArrowLeft,
  LucideCircleAlert,
  LucideCircleCheck,
  LucideEye,
  LucideEyeOff,
  LucideLoaderCircle,
  LucideMail,
  LucideRefreshCw,
  LucideShieldCheck,
} from '@lucide/angular';
import { AuthService } from '../../../core/auth/auth.service';
import { AuthLayout } from '../shared/auth-layout/auth-layout';

type RecoveryStep = 'request' | 'verify' | 'new_password' | 'success';

@Component({
  selector: 'situr-forgot-password',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    AuthLayout,
    LucideArrowLeft,
    LucideMail,
    LucideEye,
    LucideEyeOff,
    LucideCircleAlert,
    LucideCircleCheck,
    LucideLoaderCircle,
    LucideRefreshCw,
    LucideShieldCheck,
  ],
  templateUrl: './forgot-password.html',
  styleUrl: './forgot-password.css',
})
export class ForgotPassword implements OnDestroy {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly step = signal<RecoveryStep>('request');
  protected readonly loading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly infoMessage = signal<string | null>(null);

  protected readonly targetEmail = signal('');
  protected readonly verifiedCode = signal('');

  protected readonly showPassword = signal(false);
  protected readonly showConfirmPassword = signal(false);

  // Temporizador para reenvío de OTP
  protected readonly resendCountdown = signal(60);
  protected readonly canResend = signal(false);
  private timerInterval: ReturnType<typeof setInterval> | null = null;

  // Formulario 1: Solicitud de correo
  protected readonly requestForm = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
  });

  // Formulario 2: Código OTP de 6 dígitos
  protected readonly verifyForm = this.fb.nonNullable.group({
    code: ['', [Validators.required, Validators.pattern(/^\d{6}$/)]],
  });

  // Formulario 3: Nueva contraseña
  protected readonly resetForm = this.fb.nonNullable.group({
    new_password: ['', [Validators.required, Validators.minLength(8)]],
    new_password_confirm: ['', [Validators.required, Validators.minLength(8)]],
  });

  ngOnDestroy(): void {
    this.clearTimer();
  }

  protected toggleShowPassword(): void {
    this.showPassword.update((v) => !v);
  }

  protected toggleShowConfirmPassword(): void {
    this.showConfirmPassword.update((v) => !v);
  }

  /** Paso 1: Enviar solicitud de código OTP */
  protected submitRequest(): void {
    if (this.requestForm.invalid) {
      this.requestForm.markAllAsTouched();
      return;
    }

    this.errorMessage.set(null);
    this.infoMessage.set(null);
    this.loading.set(true);

    const email = this.requestForm.getRawValue().email.trim();
    this.targetEmail.set(email);

    this.auth.requestPasswordResetOtp(email).subscribe({
      next: (res) => {
        this.loading.set(false);
        this.infoMessage.set(res.detail);
        this.step.set('verify');
        this.startTimer();
      },
      error: (err: Error) => {
        this.loading.set(false);
        this.errorMessage.set(err.message);
      },
    });
  }

  /** Paso 2: Verificar el código OTP */
  protected submitVerify(): void {
    if (this.verifyForm.invalid) {
      this.verifyForm.markAllAsTouched();
      return;
    }

    this.errorMessage.set(null);
    this.infoMessage.set(null);
    this.loading.set(true);

    const code = this.verifyForm.getRawValue().code.trim();
    const email = this.targetEmail();

    this.auth.verifyPasswordResetOtp(email, code).subscribe({
      next: () => {
        this.loading.set(false);
        this.verifiedCode.set(code);
        this.step.set('new_password');
      },
      error: (err: Error) => {
        this.loading.set(false);
        this.errorMessage.set(err.message);
      },
    });
  }

  /** Reenviar código OTP */
  protected resendCode(): void {
    if (!this.canResend() || this.loading()) return;

    this.loading.set(true);
    this.errorMessage.set(null);
    this.infoMessage.set(null);

    const email = this.targetEmail();
    this.auth.requestPasswordResetOtp(email).subscribe({
      next: (res) => {
        this.loading.set(false);
        this.infoMessage.set('Se ha enviado un nuevo código a tu correo.');
        this.startTimer();
      },
      error: (err: Error) => {
        this.loading.set(false);
        this.errorMessage.set(err.message);
      },
    });
  }

  /** Cambiar de correo (regresar al paso 1) */
  protected backToEmail(): void {
    this.clearTimer();
    this.errorMessage.set(null);
    this.infoMessage.set(null);
    this.verifyForm.reset();
    this.step.set('request');
  }

  /** Paso 3: Confirmar nueva contraseña */
  protected submitNewPassword(): void {
    if (this.resetForm.invalid) {
      this.resetForm.markAllAsTouched();
      return;
    }

    const { new_password, new_password_confirm } = this.resetForm.getRawValue();
    if (new_password !== new_password_confirm) {
      this.errorMessage.set('Las contraseñas no coinciden.');
      return;
    }

    this.errorMessage.set(null);
    this.loading.set(true);

    const email = this.targetEmail();
    const code = this.verifiedCode();

    this.auth
      .confirmPasswordReset({
        email,
        code,
        new_password,
        new_password_confirm,
      })
      .subscribe({
        next: () => {
          this.loading.set(false);
          this.step.set('success');
        },
        error: (err: Error) => {
          this.loading.set(false);
          this.errorMessage.set(err.message);
        },
      });
  }

  /** Iniciar contador regresivo para reenvío */
  private startTimer(): void {
    this.clearTimer();
    this.resendCountdown.set(60);
    this.canResend.set(false);

    this.timerInterval = setInterval(() => {
      const current = this.resendCountdown();
      if (current <= 1) {
        this.clearTimer();
        this.canResend.set(true);
      } else {
        this.resendCountdown.set(current - 1);
      }
    }, 1000);
  }

  private clearTimer(): void {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
  }
}
