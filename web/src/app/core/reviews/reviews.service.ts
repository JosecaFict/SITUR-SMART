import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ProductReview, ReviewPage, ReviewPayload } from './reviews.models';

@Injectable({ providedIn: 'root' })
export class ReviewsService {
  private readonly http = inject(HttpClient);

  list(productId: number, page = 1): Observable<ReviewPage> {
    return this.http.get<ReviewPage>(`${environment.apiUrl}/marketplace/productos/${productId}/resenas/`, {
      params: { page },
    });
  }

  own(productId: number): Observable<ProductReview | null> {
    return this.http.get<{ resena: ProductReview | null }>(`${environment.apiUrl}/me/productos/${productId}/resena/`)
      .pipe(map((response) => response.resena));
  }

  create(productId: number, payload: ReviewPayload): Observable<ProductReview> {
    return this.http.post<ProductReview>(`${environment.apiUrl}/marketplace/productos/${productId}/resenas/`, payload);
  }

  update(reviewId: number, payload: ReviewPayload): Observable<ProductReview> {
    return this.http.patch<ProductReview>(`${environment.apiUrl}/me/resenas/${reviewId}/`, payload);
  }

  delete(reviewId: number): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/me/resenas/${reviewId}/`);
  }
}
