import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { RouterOutlet, provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { of } from 'rxjs';
import { routes } from '../../../app.routes';
import { AuthService } from '../../../core/auth/auth.service';
import { AppShell } from '../../../core/layout/app-shell/app-shell';
import { ProductsService } from '../../../core/products/products.service';
import { TourismProduct } from '../../../core/products/products.models';
import { MyPlanService } from '../../../core/subscription/my-plan.service';
import { ToursService } from '../../../core/tours/tours.service';
import { TravelerService } from '../../../core/traveler/traveler.service';
import { ProductoPublico } from './producto-publico';

describe('ProductoPublico: layout según sesión', () => {
  const logged = signal(false);
  let products: jasmine.SpyObj<ProductsService>;

  beforeEach(async () => {
    logged.set(false);
    products = jasmine.createSpyObj<ProductsService>('ProductsService', ['getPublic']);
    products.getPublic.and.returnValue(of({ id: 71 } as TourismProduct));
    await TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        { provide: AuthService, useValue: { isAuthenticated: logged, session: signal(null) } },
        { provide: ProductsService, useValue: products },
        { provide: TravelerService, useValue: { itineraries: () => of([]), unread: signal(0) } },
        { provide: MyPlanService, useValue: { get: () => of(null) } },
        // La ficha de un tour (CU20) se pide aparte; aquí no hace falta.
        { provide: ToursService, useValue: { getPublic: () => of(null) } },
      ],
    })
      .overrideComponent(AppShell, {
        set: { imports: [RouterOutlet], template: '<span id="panel-layout">Panel</span><router-outlet />' },
      })
      .overrideComponent(ProductoPublico, {
        set: { imports: [], template: '<span id="product-layout">{{ inShell ? "panel" : "público" }}</span>' },
      })
      .compileComponents();
  });

  it('conserva la URL pública sin iniciar sesión', async () => {
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl('/marketplace/productos/71');
    expect(harness.routeNativeElement?.querySelector('#panel-layout')).toBeNull();
    expect(harness.routeNativeElement?.querySelector('#product-layout')?.textContent).toBe('público');
    expect(products.getPublic).toHaveBeenCalledWith(71);
  });

  it('monta la misma ficha en el layout lateral con sesión', async () => {
    logged.set(true);
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl('/marketplace/productos/71');
    expect(harness.routeNativeElement?.querySelector('#panel-layout')).not.toBeNull();
    expect(harness.routeNativeElement?.querySelector('#product-layout')?.textContent).toBe('panel');
    expect(products.getPublic).toHaveBeenCalledWith(71);
  });
});
