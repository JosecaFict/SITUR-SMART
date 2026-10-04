import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';

/**
 * El scaffold original esperaba `<h1>Hello, web</h1>`, texto que dejó de existir
 * cuando se reemplazó la plantilla por el router. La prueba quedó roja sin que
 * nadie lo notara, porque nada la ejecuta automáticamente.
 *
 * Se afirma lo que el componente realmente es hoy: un contenedor cuyo único
 * trabajo es montar el router. Necesita `provideRouter` porque la plantilla
 * declara `<router-outlet>`.
 */
describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([])],
    }).compileComponents();
  });

  it('se construye', () => {
    const fixture = TestBed.createComponent(App);

    expect(fixture.componentInstance).toBeTruthy();
  });

  it('monta el router-outlet', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('router-outlet')).not.toBeNull();
  });
});
