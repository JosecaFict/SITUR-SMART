import { Component, computed, inject, signal } from '@angular/core';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import {
  LucideCircleCheck,
  LucideEye,
  LucideEyeOff,
  LucideLoaderCircle,
  LucideMail,
  LucidePhone,
  LucideUser,
} from '@lucide/angular';
import { AuthLayout } from '../shared/auth-layout/auth-layout';
import { AuthService } from '../../../core/auth/auth.service';

function passwordsMatchValidator(group: AbstractControl): ValidationErrors | null {
  const password = group.get('password')?.value;
  const confirmPassword = group.get('confirmPassword')?.value;
  return password === confirmPassword ? null : { mismatch: true };
}

const STRENGTH_LABELS = ['Muy débil', 'Débil', 'Regular', 'Buena', 'Fuerte'];
const STRENGTH_COLORS = ['bg-red-400', 'bg-red-400', 'bg-orange-400', 'bg-yellow-400', 'bg-accent'];

@Component({
  selector: 'situr-register',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    AuthLayout,
    LucideUser,
    LucideMail,
    LucidePhone,
    LucideEye,
    LucideEyeOff,
    LucideCircleCheck,
    LucideLoaderCircle,
  ],
  templateUrl: './register.html',
  styleUrl: './register.css',
})
export class Register {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly showPassword = signal(false);
  protected readonly showConfirmPassword = signal(false);
  protected readonly loading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly success = signal(false);
  protected readonly passwordValue = signal('');

  protected readonly strengthScore = computed(() => this.calculateStrength(this.passwordValue()));
  protected readonly strengthLabel = computed(() => STRENGTH_LABELS[this.strengthScore()]);
  protected readonly strengthColor = computed(() => STRENGTH_COLORS[this.strengthScore()]);

  protected readonly form = this.fb.nonNullable.group(
    {
      nombres: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
      apellidos: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
      email: ['', [Validators.required, Validators.email]],
      telefono: [''],
      password: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', [Validators.required]],
    },
    { validators: passwordsMatchValidator },
  );

  protected togglePassword(): void {
    this.showPassword.update((v) => !v);
  }

  protected toggleConfirmPassword(): void {
    this.showConfirmPassword.update((v) => !v);
  }

  protected onPasswordInput(value: string): void {
    this.passwordValue.set(value);
  }

  protected submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.errorMessage.set(null);
    this.loading.set(true);

    const { nombres, apellidos, email, password, telefono } = this.form.getRawValue();

    this.auth
      .register({
        nombres,
        apellidos,
        email,
        password,
        telefono: telefono || null,
      })
      .subscribe({
        next: () => {
          this.loading.set(false);
          this.success.set(true);
        },
        error: (err: Error) => {
          this.loading.set(false);
          this.errorMessage.set(err.message);
        },
      });
  }

  protected continueToApp(): void {
    this.router.navigateByUrl('/perfil');
  }


  private calculateStrength(password: string): number {
    if (!password) {
      return 0;
    }
    let score = 0;
    if (password.length >= 8) score++;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
    if (/\d/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;
    return Math.max(1, score);
  }
}
