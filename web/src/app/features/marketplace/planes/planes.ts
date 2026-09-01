import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LucideCheck } from '@lucide/angular';

interface Plan {
  nombre: string;
  descripcion: string;
  precio: string;
  destacado: boolean;
  cta: string;
  caracteristicas: string[];
}

const PLANES: Plan[] = [
  {
    nombre: 'Básico',
    descripcion: 'Para guías independientes y operadores que recién empiezan.',
    precio: '149',
    destacado: false,
    cta: 'Elegir Básico',
    caracteristicas: [
      'Hasta 3 usuarios de tu equipo',
      'Hasta 15 productos publicados',
      'Comisión del 8% por reserva',
      'Gestión básica de disponibilidad',
      'Soporte por correo',
    ],
  },
  {
    nombre: 'Profesional',
    descripcion: 'Para empresas en crecimiento con varios productos activos.',
    precio: '349',
    destacado: true,
    cta: 'Elegir Profesional',
    caracteristicas: [
      'Hasta 10 usuarios de tu equipo',
      'Hasta 60 productos publicados',
      'Comisión del 5% por reserva',
      'Reportes y estadísticas avanzadas',
      'Soporte prioritario',
    ],
  },
  {
    nombre: 'Empresarial',
    descripcion: 'Para cadenas y operadores con múltiples sucursales.',
    precio: '799',
    destacado: false,
    cta: 'Elegir Empresarial',
    caracteristicas: [
      'Usuarios ilimitados en tu equipo',
      'Productos publicados ilimitados',
      'Comisión del 3% por reserva',
      'Gestor de cuenta dedicado',
      'Soporte para múltiples sucursales',
    ],
  },
];

@Component({
  selector: 'situr-planes',
  imports: [RouterLink, LucideCheck],
  templateUrl: './planes.html',
  styleUrl: './planes.css',
})
export class Planes {
  protected readonly planes = PLANES;
}
