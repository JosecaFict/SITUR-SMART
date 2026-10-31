import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { ProductReview, ReviewPage } from '../../core/reviews/reviews.models';
import { ReviewsService } from '../../core/reviews/reviews.service';
import { Resenas } from './resenas';

describe('Resenas', () => {
  const logged = signal(true);
  const own: ProductReview = {
    id: 31, producto_id: 7, autor: 'Ana', es_propia: true,
    calificacion: 4, comentario: 'Buena experiencia',
    creado_en: '2026-10-20T10:00:00Z', actualizado_en: '2026-10-20T10:00:00Z',
  };
  const empty: ReviewPage = {
    count: 0, next: null, previous: null, results: [],
    distribucion_calificaciones: { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 },
  };
  let fixture: ComponentFixture<Resenas>;
  let service: jasmine.SpyObj<ReviewsService>;
  const el = () => fixture.nativeElement as HTMLElement;
  const button = (label: string) => Array.from(el().querySelectorAll('button'))
    .find((item) => item.textContent?.trim().includes(label)) as HTMLButtonElement;

  function render(): void {
    fixture = TestBed.createComponent(Resenas);
    fixture.componentRef.setInput('productId', 7);
    fixture.componentRef.setInput('average', null);
    fixture.componentRef.setInput('count', 0);
    fixture.detectChanges();
  }

  function comment(value: string): void {
    const textarea = el().querySelector('textarea') as HTMLTextAreaElement;
    textarea.value = value;
    textarea.dispatchEvent(new Event('input'));
    fixture.detectChanges();
  }

  beforeEach(async () => {
    logged.set(true);
    service = jasmine.createSpyObj<ReviewsService>('ReviewsService', ['list', 'own', 'create', 'update', 'delete']);
    service.list.and.returnValue(of(empty));
    service.own.and.returnValue(of(null));
    await TestBed.configureTestingModule({
      imports: [Resenas],
      providers: [
        provideRouter([]),
        { provide: ReviewsService, useValue: service },
        { provide: AuthService, useValue: { isAuthenticated: logged } },
      ],
    }).compileComponents();
  });

  it('permite consultar reseñas sin sesión y ofrece iniciar sesión', () => {
    logged.set(false);
    render();
    expect(service.list).toHaveBeenCalledWith(7, 1);
    expect(service.own).not.toHaveBeenCalled();
    expect(el().textContent).toContain('Todavía no hay opiniones');
    expect(el().querySelector('a[href^="/login"]')).not.toBeNull();
    expect(el().querySelector('textarea[disabled]')).not.toBeNull();
    expect(button('Publicar reseña')).toBeUndefined();
  });

  it('valida estrellas y comentario antes de publicar', () => {
    render();
    button('Publicar reseña').click();
    fixture.detectChanges();
    expect(el().textContent).toContain('Selecciona una calificación');
    (el().querySelector('button[aria-label="5 estrellas"]') as HTMLButtonElement).click();
    button('Publicar reseña').click();
    fixture.detectChanges();
    expect(el().textContent).toContain('Escribe un comentario');
    expect(service.create).not.toHaveBeenCalled();
  });

  it('publica, recarga el listado y avisa al padre para actualizar el promedio', () => {
    service.create.and.returnValue(of(own));
    render();
    const changed = jasmine.createSpy('changed');
    fixture.componentInstance.changed.subscribe(changed);
    (el().querySelector('button[aria-label="4 estrellas"]') as HTMLButtonElement).click();
    comment(' Buena experiencia ');
    button('Publicar reseña').click();
    fixture.detectChanges();
    expect(service.create).toHaveBeenCalledWith(7, { calificacion: 4, comentario: 'Buena experiencia' });
    expect(service.list).toHaveBeenCalledTimes(2);
    expect(changed).toHaveBeenCalled();
    expect(el().textContent).toContain('Tu reseña se publicó');
    expect(button('Publicar reseña')).toBeUndefined();
  });

  it('detecta una reseña propia aunque no esté en la página visible y permite editarla', () => {
    service.list.and.returnValue(of({
      count: 15, next: 'page=2', previous: null, results: [],
      distribucion_calificaciones: { 1: 0, 2: 0, 3: 0, 4: 15, 5: 0 },
    }));
    service.own.and.returnValue(of(own));
    service.update.and.returnValue(of({ ...own, calificacion: 5, comentario: 'Excelente' }));
    render();
    expect(button('Publicar reseña')).toBeUndefined();
    button('Editar mi reseña').click();
    fixture.detectChanges();
    expect(el().textContent).toContain('Editar tu reseña');
    expect((el().querySelector('textarea') as HTMLTextAreaElement).value).toBe('Buena experiencia');
    expect(el().textContent).toContain('17 caracteres');
    (el().querySelector('button[aria-label="5 estrellas"]') as HTMLButtonElement).click();
    comment('Excelente');
    button('Guardar cambios').click();
    fixture.detectChanges();
    expect(service.update).toHaveBeenCalledWith(31, { calificacion: 5, comentario: 'Excelente' });
  });

  it('pide confirmación antes de eliminar y actualiza el listado', () => {
    service.own.and.returnValue(of(own));
    service.delete.and.returnValue(of(undefined));
    render();
    const confirm = spyOn(window, 'confirm').and.returnValue(false);
    button('Eliminar').click();
    expect(service.delete).not.toHaveBeenCalled();
    confirm.and.returnValue(true);
    button('Eliminar').click();
    fixture.detectChanges();
    expect(service.delete).toHaveBeenCalledWith(31);
    expect(el().textContent).toContain('Tu reseña se eliminó');
  });

  it('muestra el error de la API y permite reintentar', () => {
    service.list.and.returnValue(throwError(() => new HttpErrorResponse({ status: 0 })));
    render();
    expect(el().textContent).toContain('No se pudo conectar');
    expect(button('Reintentar')).toBeDefined();
  });

  it('muestra el desglose real del producto completo', () => {
    service.list.and.returnValue(of({
      count: 3, next: null, previous: null, results: [own],
      distribucion_calificaciones: { 1: 0, 2: 1, 3: 0, 4: 1, 5: 1 },
    }));
    render();
    expect(el().querySelector('[aria-label="5 estrellas"]')?.getAttribute('aria-valuenow')).toBe('1');
    expect(el().querySelector('[aria-label="2 estrellas"]')?.getAttribute('aria-valuemax')).toBe('3');
  });
});
