import { Component, OnDestroy, signal } from '@angular/core';

@Component({
  selector: 'situr-auth-layout',
  imports: [],
  templateUrl: './auth-layout.html',
  styleUrl: './auth-layout.css',
})
export class AuthLayout implements OnDestroy {
  protected readonly slides = [
    { src: '/images/auth-carousel/Imagen1-mejorada.png', label: 'Destino turístico' },
    { src: '/images/auth-carousel/Imagen2-mejorada.png', label: 'Laguna y flamencos' },
    { src: '/images/auth-carousel/Imagen3-mejorada.png', label: 'Cultura y patrimonio' },
    { src: '/images/auth-carousel/Hotel1.jpg', label: 'Hospedaje y descanso' },
    { src: '/images/auth-carousel/Imagen4-mejorada.png', label: 'Ciudad colonial' },
    { src: '/images/auth-carousel/Hotel2-mejorada.png', label: 'Hotel y piscina' },
    { src: '/images/auth-carousel/Imagen5-mejorada.png', label: 'Experiencias urbanas' },
    { src: '/images/auth-carousel/Hotel3-mejorada.png', label: 'Gran Hotel Cochabamba' },
    { src: '/images/auth-carousel/Imagen6-mejorada.png', label: 'Arquitectura hotelera' },
    { src: '/images/auth-carousel/Hotel4.webp', label: 'Experiencia de hotel' },
    { src: '/images/auth-carousel/Imagen7-mejorada.png', label: 'Patrimonio arqueológico' },
  ];

  protected readonly activeSlide = signal(0);

  protected readonly stats = [
    { value: '1.2K+', label: 'Destinos' },
    { value: '48K', label: 'Visitantes' },
    { value: '99.9%', label: 'Disponibilidad' },
  ];

  private carouselTimer?: ReturnType<typeof setInterval>;

  constructor() {
    this.startCarousel();
  }

  ngOnDestroy(): void {
    this.stopCarousel();
  }

  protected selectSlide(index: number): void {
    this.activeSlide.set(index);
    this.startCarousel();
  }

  protected pauseCarousel(): void {
    this.stopCarousel();
  }

  protected resumeCarousel(): void {
    this.startCarousel();
  }

  protected hideBrokenImage(event: Event): void {
    const image = event.target as HTMLImageElement;
    image.style.display = 'none';
  }

  private startCarousel(): void {
    this.stopCarousel();
    this.carouselTimer = setInterval(() => {
      this.activeSlide.update((current) => (current + 1) % this.slides.length);
    }, 4000);
  }

  private stopCarousel(): void {
    if (this.carouselTimer) {
      clearInterval(this.carouselTimer);
      this.carouselTimer = undefined;
    }
  }
}
