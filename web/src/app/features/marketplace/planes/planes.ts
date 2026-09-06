import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LucideCheck } from '@lucide/angular';
import { CompaniesService } from '../../../core/companies/companies.service';
import { Plan } from '../../../core/companies/companies.models';

@Component({
  selector: 'situr-planes',
  imports: [RouterLink, LucideCheck],
  templateUrl: './planes.html',
  styleUrl: './planes.css',
})
export class Planes implements OnInit {
  private readonly companiesService = inject(CompaniesService);

  protected readonly planes = signal<Plan[]>([]);
  protected readonly loading = signal(true);
  protected readonly errorMessage = signal<string | null>(null);

  ngOnInit(): void {
    this.companiesService.listPlans().subscribe({
      next: (planes) => {
        this.planes.set(planes);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.errorMessage.set(
          error.status === 0
            ? 'No se pudo conectar con el backend. Verifica que Django esté iniciado.'
            : 'No fue posible cargar los planes disponibles.',
        );
      },
    });
  }

  protected destacado(plan: Plan): boolean {
    return plan.codigo === 'PROFESIONAL';
  }

  protected caracteristicas(plan: Plan): string[] {
    const usuarios = plan.max_usuarios >= 999999 ? 'Usuarios ilimitados' : `Hasta ${plan.max_usuarios} usuarios de tu equipo`;
    const productos =
      plan.max_productos >= 999999
        ? 'Productos publicados ilimitados'
        : `Hasta ${plan.max_productos} productos publicados`;
    return [usuarios, productos, `Comisión del ${plan.porcentaje_comision}% por reserva`];
  }
}
