import { Component } from '@angular/core';
import { LucideCompass, LucideMapPin } from '@lucide/angular';

@Component({
  selector: 'situr-auth-layout',
  imports: [LucideCompass, LucideMapPin],
  templateUrl: './auth-layout.html',
  styleUrl: './auth-layout.css',
})
export class AuthLayout {
  protected readonly stats = [
    { value: '1.2K+', label: 'Destinos' },
    { value: '48K', label: 'Visitantes' },
    { value: '99.9%', label: 'Disponibilidad' },
  ];
}
