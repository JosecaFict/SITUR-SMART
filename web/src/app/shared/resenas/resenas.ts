import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, input, output, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { LucidePencil, LucideStar, LucideTrash2 } from '@lucide/angular';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error';
import { ProductReview, ReviewPage } from '../../core/reviews/reviews.models';
import { ReviewsService } from '../../core/reviews/reviews.service';

@Component({
  selector: 'situr-resenas',
  imports: [RouterLink, LucidePencil, LucideStar, LucideTrash2],
  templateUrl: './resenas.html',
})
export class Resenas implements OnInit {
  private readonly reviewsService = inject(ReviewsService);
  private readonly router = inject(Router);
  protected readonly auth = inject(AuthService);

  readonly productId = input.required<number>();
  readonly average = input<number | null>(null);
  readonly count = input(0);
  readonly changed = output<void>();

  protected readonly stars = [1, 2, 3, 4, 5];
  protected readonly distributionStars = [5, 4, 3, 2, 1] as const;
  protected readonly Math = Math;
  protected readonly reviews = signal<ProductReview[]>([]);
  protected readonly distribution = signal<ReviewPage['distribucion_calificaciones'] | null>(null);
  protected readonly page = signal(1);
  protected readonly total = signal(0);
  protected readonly pageCount = computed(() => Math.max(1, Math.ceil(this.total() / 10)));
  protected readonly loading = signal(true);
  protected readonly listError = signal<string | null>(null);
  protected readonly ownReview = signal<ProductReview | null>(null);
  protected readonly ownLoading = signal(false);
  protected readonly ownError = signal<string | null>(null);
  protected readonly editing = signal(false);
  protected readonly rating = signal(0);
  protected readonly comment = signal('');
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly loginUrl = computed(() => ['/login'] as const);
  protected readonly returnUrl = computed(() => ({ returnUrl: this.router.url }));

  ngOnInit(): void {
    this.loadReviews();
    if (this.auth.isAuthenticated()) this.loadOwn();
  }

  protected loadReviews(): void {
    this.loading.set(true);
    this.listError.set(null);
    this.reviewsService.list(this.productId(), this.page()).subscribe({
      next: (result) => {
        this.reviews.set(result.results);
        this.total.set(result.count);
        this.distribution.set(result.distribucion_calificaciones);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.distribution.set(null);
        this.listError.set(apiErrorMessage(error, 'No se pudieron cargar las reseñas.'));
      },
    });
  }

  protected loadOwn(): void {
    this.ownLoading.set(true);
    this.ownError.set(null);
    this.reviewsService.own(this.productId()).subscribe({
      next: (review) => {
        this.ownReview.set(review);
        this.ownLoading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.ownLoading.set(false);
        this.ownError.set(apiErrorMessage(error, 'No se pudo comprobar tu reseña.'));
      },
    });
  }

  protected selectPage(page: number): void {
    if (page < 1 || page > this.pageCount() || this.loading()) return;
    this.page.set(page);
    this.loadReviews();
  }

  protected dateLabel(value: string): string {
    return new Intl.DateTimeFormat('es-BO', {
      day: 'numeric', month: 'long', year: 'numeric', timeZone: 'America/La_Paz',
    }).format(new Date(value));
  }

  protected initials(name: string): string {
    const parts = name.trim().split(/\s+/).filter(Boolean);
    return parts.length ? parts.slice(0, 2).map((part) => part[0].toUpperCase()).join('') : 'V';
  }

  protected ratingCount(star: 1 | 2 | 3 | 4 | 5): number {
    return this.distribution()?.[star] ?? 0;
  }

  protected barWidth(star: 1 | 2 | 3 | 4 | 5): number {
    return this.total() ? Math.round(this.ratingCount(star) * 100 / this.total()) : 0;
  }

  protected startEdit(): void {
    const review = this.ownReview();
    if (!review) return;
    this.rating.set(review.calificacion);
    this.comment.set(review.comentario);
    this.formError.set(null);
    this.notice.set(null);
    this.editing.set(true);
  }

  protected cancelEdit(): void {
    this.editing.set(false);
    this.rating.set(0);
    this.comment.set('');
    this.formError.set(null);
  }

  protected submit(): void {
    if (this.saving() || this.ownLoading() || this.ownError()) return;
    const comment = this.comment().trim();
    if (this.rating() < 1 || this.rating() > 5) {
      this.formError.set('Selecciona una calificación de 1 a 5 estrellas.');
      return;
    }
    if (!comment) {
      this.formError.set('Escribe un comentario antes de publicar.');
      return;
    }
    const current = this.ownReview();
    if (current && !this.editing()) return;
    this.formError.set(null);
    this.notice.set(null);
    this.saving.set(true);
    const payload = { calificacion: this.rating(), comentario: comment };
    const request = current
      ? this.reviewsService.update(current.id, payload)
      : this.reviewsService.create(this.productId(), payload);
    request.subscribe({
      next: (review) => {
        this.saving.set(false);
        this.ownReview.set(review);
        this.cancelEdit();
        this.notice.set(current ? 'Tu reseña se actualizó.' : 'Tu reseña se publicó.');
        this.page.set(1);
        this.loadReviews();
        this.changed.emit();
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.formError.set(apiErrorMessage(error, 'No se pudo guardar tu reseña.'));
        // Otro dispositivo pudo crearla primero. Reconsultar evita un segundo formulario.
        if (error.status === 400) this.loadOwn();
      },
    });
  }

  protected remove(): void {
    const review = this.ownReview();
    if (!review || this.saving() || !window.confirm('¿Eliminar tu reseña de este producto?')) return;
    this.saving.set(true);
    this.formError.set(null);
    this.reviewsService.delete(review.id).subscribe({
      next: () => {
        this.saving.set(false);
        this.ownReview.set(null);
        this.cancelEdit();
        this.notice.set('Tu reseña se eliminó.');
        this.page.set(1);
        this.loadReviews();
        this.changed.emit();
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.formError.set(apiErrorMessage(error, 'No se pudo eliminar tu reseña.'));
      },
    });
  }
}
