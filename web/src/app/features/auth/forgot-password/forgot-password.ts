import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { LucideLoaderCircle, LucideMail, LucideSend } from '@lucide/angular';
import { AuthLayout } from '../shared/auth-layout/auth-layout';
import { AuthService } from '../../../core/auth/auth.service';

@Component({
  selector: 'situr-forgot-password',
  imports: [ReactiveFormsModule, RouterLink, AuthLayout, LucideMail, LucideSend, LucideLoaderCircle],
  templateUrl: './forgot-password.html',
  styleUrl: './forgot-password.css',
})
export class ForgotPassword {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);

  protected readonly loading = signal(false);
  protected readonly sentTo = signal<string | null>(null);

  protected readonly form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
  });

  protected submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.loading.set(true);
    const { email } = this.form.getRawValue();

    this.auth.requestPasswordReset(email).subscribe(({ email: sent }) => {
      this.loading.set(false);
      this.sentTo.set(sent);
    });
  }
}
