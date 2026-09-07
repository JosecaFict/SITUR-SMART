import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  LucideCalendar,
  LucideCheckCircle2,
  LucideCircleAlert,
  LucideCompass,
  LucideFileText,
  LucideLoaderCircle,
  LucideMail,
  LucidePhone,
  LucideShieldCheck,
  LucideSparkles,
  LucideUser,
} from '@lucide/angular';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'situr-perfil',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    LucideUser,
    LucideMail,
    LucidePhone,
    LucideFileText,
    LucideCalendar,
    LucideCheckCircle2,
    LucideCircleAlert,
    LucideLoaderCircle,
    LucideShieldCheck,
    LucideSparkles,
    LucideCompass,
  ],
  templateUrl: './perfil.html',
  styleUrl: './perfil.css',
})
export class Perfil implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);

  protected readonly session = this.auth.session;
  protected readonly loading = signal(false);
  protected readonly successMessage = signal<string | null>(null);
  protected readonly errorMessage = signal<string | null>(null);

  protected readonly isCliente = computed(() => {
    const roles = this.session()?.user.roles ?? [];
    return roles.includes('CLIENTE');
  });

  protected readonly isSuperAdmin = computed(() => this.auth.isSuperAdmin());

  protected readonly roleBadge = computed(() => {
    if (this.isSuperAdmin()) return 'Super Administrador';
    if (this.isCliente()) return 'Viajero / Turista';
    return 'Prestador Turístico';
  });

  protected readonly userInitials = computed(() => {
    const user = this.session()?.user;
    if (!user) return 'U';
    const first = user.nombres?.charAt(0) ?? '';
    const last = user.apellidos?.charAt(0) ?? '';
    return `${first}${last}`.toUpperCase() || 'U';
  });

  protected readonly form = this.fb.nonNullable.group({
    nombres: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    apellidos: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    telefono: [''],
    tipo_documento: ['CI'],
    numero_documento: [''],
    fecha_nacimiento: [''],
  });

  ngOnInit(): void {
    const user = this.session()?.user;
    if (user) {
      this.form.patchValue({
        nombres: user.nombres || '',
        apellidos: user.apellidos || '',
        telefono: user.telefono || '',
        tipo_documento: user.perfil?.tipo_documento || 'CI',
        numero_documento: user.perfil?.numero_documento || '',
        fecha_nacimiento: user.perfil?.fecha_nacimiento || '',
      });
    }
  }

  protected saveProfile(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.loading.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);

    const raw = this.form.getRawValue();

    this.auth
      .updateProfile({
        nombres: raw.nombres.trim(),
        apellidos: raw.apellidos.trim(),
        telefono: raw.telefono.trim() || null,
        tipo_documento: raw.tipo_documento.trim() || null,
        numero_documento: raw.numero_documento.trim() || null,
        fecha_nacimiento: raw.fecha_nacimiento || null,
      })
      .subscribe({
        next: () => {
          this.loading.set(false);
          this.successMessage.set('Tus datos se actualizaron correctamente.');
          setTimeout(() => this.successMessage.set(null), 5000);
        },
        error: (err: Error) => {
          this.loading.set(false);
          this.errorMessage.set(err.message || 'No fue posible actualizar tus datos.');
        },
      });
  }
}
