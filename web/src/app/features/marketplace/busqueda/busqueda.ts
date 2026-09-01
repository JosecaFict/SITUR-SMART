import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LucideCalendar, LucideChevronDown, LucideMapPin, LucideSearch } from '@lucide/angular';

interface ProductoDestacado {
  imagen: string;
  tipo: string;
  titulo: string;
  ciudad: string;
  operador: string;
  precio: string;
  unidad: string;
}

const PRODUCTOS_DESTACADOS: ProductoDestacado[] = [
  {
    imagen: '/images/auth-carousel/Hotel4.webp',
    tipo: 'HOTEL',
    titulo: 'Hotel Kachi Wasi',
    ciudad: 'La Paz, Bolivia',
    operador: 'Andes Boutique Hotels',
    precio: 'Bs 450',
    unidad: '/ noche',
  },
  {
    imagen: '/images/auth-carousel/Hotel1.jpg',
    tipo: 'HOTEL',
    titulo: 'Resort Laguna Urubó',
    ciudad: 'Santa Cruz de la Sierra, Bolivia',
    operador: 'Cruceña Hospitality',
    precio: 'Bs 620',
    unidad: '/ noche',
  },
  {
    imagen: '/images/auth-carousel/Imagen1-mejorada.png',
    tipo: 'TOUR',
    titulo: 'Teleférico y Miradores de La Paz',
    ciudad: 'La Paz, Bolivia',
    operador: 'Kanata Turismo',
    precio: 'Bs 120',
    unidad: '/ persona',
  },
  {
    imagen: '/images/auth-carousel/Imagen3-mejorada.png',
    tipo: 'EXPERIENCIA',
    titulo: 'Catedral y Casco Viejo al Atardecer',
    ciudad: 'Santa Cruz de la Sierra, Bolivia',
    operador: 'Raíces Cruceñas',
    precio: 'Bs 80',
    unidad: '/ persona',
  },
  {
    imagen: '/images/auth-carousel/Imagen5-mejorada.png',
    tipo: 'TOUR',
    titulo: 'Centro Histórico de Sucre',
    ciudad: 'Sucre, Bolivia',
    operador: 'Valle Alto Tours',
    precio: 'Bs 90',
    unidad: '/ persona',
  },
  {
    imagen: '/images/auth-carousel/Imagen7-mejorada.png',
    tipo: 'ATRACCIÓN',
    titulo: 'Fuerte de Samaipata (Sitio UNESCO)',
    ciudad: 'Samaipata, Bolivia',
    operador: 'Raíces Cruceñas',
    precio: 'Bs 60',
    unidad: '/ persona',
  },
];

const FILTROS_TIPO = ['Todos', 'Hoteles', 'Tours', 'Experiencias', 'Atracciones'] as const;

@Component({
  selector: 'situr-busqueda',
  imports: [RouterLink, LucideSearch, LucideMapPin, LucideCalendar, LucideChevronDown],
  templateUrl: './busqueda.html',
  styleUrl: './busqueda.css',
})
export class Busqueda {
  protected readonly productos = PRODUCTOS_DESTACADOS;
  protected readonly filtros = FILTROS_TIPO;
}
