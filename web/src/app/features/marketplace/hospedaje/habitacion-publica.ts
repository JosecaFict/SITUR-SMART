import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import {
  LucideArrowLeft, LucideBedDouble, LucideBuilding2, LucideCircleAlert, LucideImage,
  LucideMapPin, LucideUsers,
} from '@lucide/angular';
import { Room } from '../../../core/lodging/lodging.models';
import { LodgingService } from '../../../core/lodging/lodging.service';

/**
 * Detalle público de un tipo de habitación.
 *
 * La URL lleva los dos identificadores, y se comprueba que la habitación
 * pertenezca al hospedaje indicado: una habitación mostrada bajo el hotel
 * equivocado sería información falsa sobre dónde se aloja el viajero. Si no
 * coinciden se trata como inexistente, sin revelar a qué hotel pertenece en
 * realidad.
 */
@Component({
  selector: 'situr-habitacion-publica',
  imports: [
    RouterLink, LucideArrowLeft, LucideBedDouble, LucideBuilding2, LucideCircleAlert,
    LucideImage, LucideMapPin, LucideUsers,
  ],
  templateUrl: './habitacion-publica.html',
})
export class HabitacionPublica implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly lodgingService = inject(LodgingService);

  protected lodgingId = 0;
  private roomId = 0;

  protected readonly room = signal<Room | null>(null);
  protected readonly loading = signal(true);
  protected readonly notFound = signal(false);
  protected readonly errorMessage = signal<string | null>(null);

  ngOnInit(): void {
    const params = this.route.snapshot.paramMap;
    this.lodgingId = Number(params.get('hospedajeId'));
    this.roomId = Number(params.get('habitacionId'));
    if (!this.lodgingId || !this.roomId) {
      this.loading.set(false);
      this.notFound.set(true);
      return;
    }
    this.loadRoom();
  }

  protected loadRoom(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    this.notFound.set(false);
    this.lodgingService.getPublicRoom(this.roomId).subscribe({
      next: (room) => {
        this.loading.set(false);
        // La habitación existe y es pública, pero puede no ser de este hotel.
        if (room.establecimiento_id !== this.lodgingId) {
          this.notFound.set(true);
          return;
        }
        this.room.set(room);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        if (error.status === 404) this.notFound.set(true);
        else this.errorMessage.set('No pudimos cargar esta habitación. Inténtalo de nuevo.');
      },
    });
  }

  /**
   * Marca que la URL de la imagen fallo, para caer al bloque de icono.
   *
   * No se reemplaza el `src` por una imagen por defecto: cambiarlo puede volver
   * a fallar y disparar `error` otra vez, en bucle.
   */
  protected readonly imageFailed = signal(false);
}
