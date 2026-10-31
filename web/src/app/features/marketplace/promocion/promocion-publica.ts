import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { LucideArrowLeft, LucideBadgePercent, LucideCalendarDays, LucideCircleAlert, LucideImage, LucidePackageOpen } from '@lucide/angular';
import { Promotion } from '../../../core/promotions/promotions.models';
import { promotionApiError, PromotionsService } from '../../../core/promotions/promotions.service';

@Component({
  selector: 'situr-promocion-publica',
  imports: [DatePipe, RouterLink, LucideArrowLeft, LucideBadgePercent, LucideCalendarDays, LucideCircleAlert, LucideImage, LucidePackageOpen],
  templateUrl: './promocion-publica.html',
})
export class PromocionPublica implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly service = inject(PromotionsService);
  protected readonly inShell = this.route.snapshot.data['inShell'] === true;
  protected readonly item = signal<Promotion | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly imageFailed = signal(false);

  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get('id') ?? this.route.parent?.snapshot.paramMap.get('id'));
    if (!Number.isInteger(id) || id <= 0) { this.loading.set(false); this.error.set('Promoción no encontrada.'); return; }
    this.service.getPublic(id).subscribe({
      next: (promotion) => {
        if (promotion.modalidad === 'EXISTENTE' && promotion.producto_id) {
          this.router.navigate(['/marketplace/productos', promotion.producto_id], { replaceUrl: true });
          return;
        }
        this.item.set(promotion); this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => { this.loading.set(false); this.error.set(promotionApiError(error, 'Esta promoción no está disponible.')); },
    });
  }
}
