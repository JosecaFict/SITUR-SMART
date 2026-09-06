import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import {
  LucideArrowLeft,
  LucideCheck,
  LucideCircleAlert,
  LucideEye,
  LucideEyeOff,
  LucideLoaderCircle,
} from '@lucide/angular';
import { AuthLayout } from '../shared/auth-layout/auth-layout';
import { AuthService } from '../../../core/auth/auth.service';
import { CompaniesService } from '../../../core/companies/companies.service';
import { Plan } from '../../../core/companies/companies.models';

@Component({
  selector: 'situr-registro',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    AuthLayout,
    LucideArrowLeft,
    LucideCheck,
    LucideCircleAlert,
    LucideEye,
    LucideEyeOff,
    LucideLoaderCircle,
  ],
  templateUrl: './registro.html',
  styleUrl: './registro.css',
})
export class Registro implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly companiesService = inject(CompaniesService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  protected readonly planes = signal<Plan[]>([]);
  protected readonly loadingPlanes = signal(true);
  protected readonly showPassword = signal(false);
  protected readonly loading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);

  protected readonly form = this.fb.nonNullable.group({
    plan_codigo: ['', Validators.required],
    razon_social: ['', [Validators.required, Validators.maxLength(180)]],
    nombre_comercial: ['', [Validators.required, Validators.maxLength(180)]],
    owner_nombres: ['', Validators.required],
    owner_apellidos: ['', Validators.required],
    owner_email: ['', [Validators.required, Validators.email]],
    owner_password: ['', [Validators.required, Validators.minLength(8)]],
  });

  ngOnInit(): void {
    const preselected = this.route.snapshot.queryParamMap.get('plan') ?? '';
    this.companiesService.listPlans().subscribe({
      next: (planes) => {
        this.planes.set(planes);
        this.loadingPlanes.set(false);
        const defaultPlan = planes.find((plan) => plan.codigo === preselected) ?? planes[0];
        if (defaultPlan) {
          this.form.controls.plan_codigo.setValue(defaultPlan.codigo);
        }
      },
      error: () => {
        this.loadingPlanes.set(false);
        this.errorMessage.set('No fue posible cargar los planes disponibles.');
      },
    });
  }

  protected togglePassword(): void {
    this.showPassword.update((v) => !v);
  }

  protected selectPlan(codigo: string): void {
    this.form.controls.plan_codigo.setValue(codigo);
  }

  protected submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.errorMessage.set(null);
    this.loading.set(true);

    const raw = this.form.getRawValue();
    const email = raw.owner_email.trim().toLowerCase();
    const password = raw.owner_password;

    this.companiesService
      .selfSignup({
        razon_social: raw.razon_social.trim(),
        nombre_comercial: raw.nombre_comercial.trim(),
        plan_codigo: raw.plan_codigo,
        propietario: {
          email,
          nombres: raw.owner_nombres.trim(),
          apellidos: raw.owner_apellidos.trim(),
          password,
        },
      })
      .subscribe({
        next: () => {
          this.auth.login({ email, password, remember: true }).subscribe({
            next: () => {
              this.loading.set(false);
              this.router.navigateByUrl('/dashboard');
            },
            error: () => {
              this.loading.set(false);
              this.router.navigate(['/login'], { queryParams: { registrado: '1' } });
            },
          });
        },
        error: (error: HttpErrorResponse) => {
          this.loading.set(false);
          this.errorMessage.set(this.apiMessage(error));
        },
      });
  }

  private apiMessage(error: HttpErrorResponse): string {
    if (error.status === 0) {
      return 'No se pudo conectar con el backend. Verifica que Django esté iniciado.';
    }
    const details = error.error?.error?.details;
    if (details && typeof details === 'object') {
      const firstKey = Object.keys(details)[0];
      const firstValue = (details as Record<string, unknown>)[firstKey];
      if (typeof firstValue === 'string') {
        return firstValue;
      }
      if (Array.isArray(firstValue) && typeof firstValue[0] === 'string') {
        return firstValue[0];
      }
    }
    return error.error?.error?.message ?? 'No fue posible completar el registro.';
  }
}
