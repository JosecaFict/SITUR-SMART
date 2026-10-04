import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable } from 'rxjs';
import {
  LucideCheck,
  LucideCircleAlert,
  LucideCirclePlus,
  LucideGlobe2,
  LucideMapPin,
  LucidePencil,
  LucideRefreshCw,
  LucideSearch,
  LucideX,
} from '@lucide/angular';
import { LatLng } from '../../../core/geo/geo.models';
import { AdminCity, AdminCountry } from '../../../core/locations/locations.models';
import { LocationsService } from '../../../core/locations/locations.service';
import { apiErrorMessage } from '../../../core/http/api-error';
import { MapaUbicacion } from '../../../shared/mapa-ubicacion/mapa-ubicacion';

type FormMode = 'country-create' | 'country-edit' | 'city-create' | 'city-edit' | null;
type PendingStatus = { kind: 'country' | 'city'; id: number; name: string; active: boolean };

@Component({
  selector: 'situr-ubicaciones',
  imports: [
    ReactiveFormsModule,
    MapaUbicacion,
    LucideCheck,
    LucideCircleAlert,
    LucideCirclePlus,
    LucideGlobe2,
    LucideMapPin,
    LucidePencil,
    LucideRefreshCw,
    LucideSearch,
    LucideX,
  ],
  templateUrl: './ubicaciones.html',
  styleUrl: './ubicaciones.css',
})
export class Ubicaciones implements OnInit {
  private readonly locations = inject(LocationsService);
  private readonly fb = inject(FormBuilder);

  protected readonly countries = signal<AdminCountry[]>([]);
  protected readonly cities = signal<AdminCity[]>([]);
  protected readonly selectedCountry = signal<AdminCountry | null>(null);
  protected readonly selectedCity = signal<AdminCity | null>(null);
  protected readonly formMode = signal<FormMode>(null);
  protected readonly pendingStatus = signal<PendingStatus | null>(null);
  protected readonly mapPoint = signal<LatLng | null>(null);
  protected readonly loading = signal(true);
  protected readonly loadingCities = signal(false);
  protected readonly saving = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly successMessage = signal<string | null>(null);
  protected readonly countrySearch = signal('');
  protected readonly citySearch = signal('');
  protected readonly activeCountries = computed(() => this.countries().filter((item) => item.activo).length);

  protected readonly countryForm = this.fb.nonNullable.group({
    codigo: ['', [Validators.required, Validators.pattern(/^[A-Z]{3}$/)]],
    nombre: ['', [Validators.required, Validators.maxLength(100)]],
  });

  protected readonly cityForm = this.fb.nonNullable.group({
    nombre: ['', [Validators.required, Validators.maxLength(120)]],
    zona_horaria: ['America/La_Paz', Validators.maxLength(80)],
  });

  ngOnInit(): void {
    this.loadCountries();
  }

  protected loadCountries(): void {
    this.loading.set(true);
    this.locations.listCountries(this.countrySearch()).subscribe({
      next: (countries) => {
        this.countries.set(countries);
        const currentId = this.selectedCountry()?.id;
        const selected = countries.find((item) => item.id === currentId) ?? countries[0] ?? null;
        this.selectedCountry.set(selected);
        this.loading.set(false);
        if (selected) this.loadCities(selected);
        else this.cities.set([]);
      },
      error: (error: HttpErrorResponse) => {
        this.loading.set(false);
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible cargar los países.'));
      },
    });
  }

  protected selectCountry(country: AdminCountry): void {
    this.selectedCountry.set(country);
    this.citySearch.set('');
    this.closeForm();
    this.loadCities(country);
  }

  protected loadCities(country = this.selectedCountry()): void {
    if (!country) return;
    this.loadingCities.set(true);
    this.locations.listCities(country.id, this.citySearch()).subscribe({
      next: (cities) => {
        this.cities.set(cities);
        this.loadingCities.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.loadingCities.set(false);
        this.errorMessage.set(apiErrorMessage(error, 'No fue posible cargar las ciudades.'));
      },
    });
  }

  protected startCountryCreate(): void {
    this.closeForm();
    this.countryForm.reset({ codigo: '', nombre: '' });
    this.formMode.set('country-create');
  }

  protected startCountryEdit(country: AdminCountry): void {
    this.closeForm();
    this.selectedCountry.set(country);
    this.countryForm.reset({ codigo: country.codigo, nombre: country.nombre });
    this.formMode.set('country-edit');
  }

  protected submitCountry(): void {
    this.countryForm.markAllAsTouched();
    if (this.countryForm.invalid) return;
    const value = this.countryForm.getRawValue();
    const request = this.formMode() === 'country-edit' && this.selectedCountry()
      ? this.locations.updateCountry(this.selectedCountry()!.id, { nombre: value.nombre.trim() })
      : this.locations.createCountry({ codigo: value.codigo.trim().toUpperCase(), nombre: value.nombre.trim() });
    this.saving.set(true);
    request.subscribe({
      next: (country) => {
        this.saving.set(false);
        this.selectedCountry.set(country);
        this.closeForm();
        this.successMessage.set('País guardado correctamente.');
        this.loadCountries();
      },
      error: (error: HttpErrorResponse) => this.failSave(error, 'No fue posible guardar el país.'),
    });
  }

  protected startCityCreate(): void {
    if (!this.selectedCountry()?.activo) return;
    this.closeForm();
    this.cityForm.reset({ nombre: '', zona_horaria: 'America/La_Paz' });
    this.mapPoint.set(null);
    this.formMode.set('city-create');
  }

  protected startCityEdit(city: AdminCity): void {
    this.closeForm();
    this.selectedCity.set(city);
    this.cityForm.reset({ nombre: city.nombre, zona_horaria: city.zona_horaria ?? '' });
    this.mapPoint.set(
      city.latitud !== null && city.longitud !== null
        ? { lat: Number(city.latitud), lng: Number(city.longitud) }
        : null,
    );
    this.formMode.set('city-edit');
  }

  protected pickPoint(point: LatLng): void {
    this.mapPoint.set({ lat: Number(point.lat.toFixed(6)), lng: Number(point.lng.toFixed(6)) });
  }

  protected submitCity(): void {
    const country = this.selectedCountry();
    this.cityForm.markAllAsTouched();
    if (!country || this.cityForm.invalid) return;
    const value = this.cityForm.getRawValue();
    const point = this.mapPoint();
    const payload = {
      nombre: value.nombre.trim(),
      pais_id: country.id,
      latitud: point ? point.lat.toFixed(6) : null,
      longitud: point ? point.lng.toFixed(6) : null,
      zona_horaria: value.zona_horaria.trim(),
    };
    const request = this.formMode() === 'city-edit' && this.selectedCity()
      ? this.locations.updateCity(this.selectedCity()!.id, payload)
      : this.locations.createCity(payload);
    this.saving.set(true);
    request.subscribe({
      next: () => {
        this.saving.set(false);
        this.closeForm();
        this.successMessage.set('Ciudad guardada correctamente.');
        this.loadCountries();
      },
      error: (error: HttpErrorResponse) => this.failSave(error, 'No fue posible guardar la ciudad.'),
    });
  }

  protected requestStatus(kind: 'country' | 'city', item: AdminCountry | AdminCity): void {
    this.pendingStatus.set({ kind, id: item.id, name: item.nombre, active: !item.activo });
  }

  protected confirmStatus(): void {
    const pending = this.pendingStatus();
    if (!pending) return;
    this.saving.set(true);
    const request: Observable<AdminCountry | AdminCity> = pending.kind === 'country'
      ? this.locations.changeCountryStatus(pending.id, pending.active)
      : this.locations.changeCityStatus(pending.id, pending.active);
    request.subscribe({
      next: () => {
        this.saving.set(false);
        this.pendingStatus.set(null);
        this.successMessage.set(`${pending.name} quedó ${pending.active ? 'activo' : 'inactivo'}.`);
        this.loadCountries();
      },
      error: (error: HttpErrorResponse) => this.failSave(error, 'No fue posible cambiar el estado.'),
    });
  }

  protected closeForm(): void {
    this.formMode.set(null);
    this.selectedCity.set(null);
    this.mapPoint.set(null);
    this.errorMessage.set(null);
  }

  protected updateCountrySearch(event: Event): void {
    this.countrySearch.set((event.target as HTMLInputElement).value);
  }

  protected updateCitySearch(event: Event): void {
    this.citySearch.set((event.target as HTMLInputElement).value);
  }

  private failSave(error: HttpErrorResponse, fallback: string): void {
    this.saving.set(false);
    this.errorMessage.set(apiErrorMessage(error, fallback));
  }
}
