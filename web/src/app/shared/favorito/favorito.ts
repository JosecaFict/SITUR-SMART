import { Component, OnInit, inject, input, signal } from '@angular/core';
import { Router } from '@angular/router';
import { LucideHeart } from '@lucide/angular';
import { AuthService } from '../../core/auth/auth.service';
import { TravelerService } from '../../core/traveler/traveler.service';

/** Corazón para guardar un producto en Favoritos. Sin sesión, lleva al login. */
@Component({
  selector: 'situr-favorito',
  imports: [LucideHeart],
  template: `
    <button type="button" (click)="toggle()" [disabled]="working()"
      [attr.aria-pressed]="favorite()" [attr.aria-label]="favorite() ? 'Quitar de favoritos' : 'Guardar en favoritos'"
      class="flex min-h-11 items-center gap-2 rounded-xl border px-4 text-sm font-semibold transition"
      [class]="favorite() ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-input-border bg-white text-label hover:bg-input-bg'">
      <svg lucideHeart class="h-4 w-4" [class.fill-current]="favorite()"></svg>
      {{ favorite() ? 'En favoritos' : 'Guardar' }}
    </button>
  `,
})
export class Favorito implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly traveler = inject(TravelerService);
  private readonly router = inject(Router);

  readonly productId = input.required<number>();
  protected readonly favorite = signal(false);
  protected readonly working = signal(false);

  ngOnInit(): void {
    if (!this.auth.isAuthenticated()) return;
    this.traveler.favorites().subscribe({
      next: (products) => this.favorite.set(products.some((product) => product.id === this.productId())),
      error: () => this.favorite.set(false),
    });
  }

  protected toggle(): void {
    if (!this.auth.isAuthenticated()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
      return;
    }
    const wasFavorite = this.favorite();
    this.favorite.set(!wasFavorite);
    this.working.set(true);
    const request = wasFavorite
      ? this.traveler.removeFavorite(this.productId())
      : this.traveler.addFavorite(this.productId());
    request.subscribe({
      next: () => this.working.set(false),
      error: () => {
        this.favorite.set(wasFavorite);
        this.working.set(false);
      },
    });
  }
}
