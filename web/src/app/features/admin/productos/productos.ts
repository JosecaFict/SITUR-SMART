import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import {
  LucideBuilding2, LucideCheck, LucideCircleAlert, LucideEye, LucideEyeOff,
  LucideImage, LucideLink, LucideMapPin, LucidePackageOpen, LucidePencil,
  LucidePlus, LucideRefreshCw, LucideSearch, LucideTrash2, LucideUpload,
  LucideUsers, LucideX,
} from '@lucide/angular';
import { forkJoin } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { City } from '../../../core/companies/companies.models';
import { CompaniesService } from '../../../core/companies/companies.service';
import { MediaService } from '../../../core/media/media.service';
import { Currency, ProductStatus, ProductType, TourismProduct } from '../../../core/products/products.models';
import { ProductsService } from '../../../core/products/products.service';

interface CompanyChoice { id: number; name: string; }
type StatusFilter = 'TODOS' | ProductStatus;

@Component({
  selector: 'situr-productos',
  imports: [
    ReactiveFormsModule, LucideBuilding2, LucideCheck, LucideCircleAlert, LucideEye, LucideEyeOff,
    LucideImage, LucideLink, LucideMapPin, LucidePackageOpen, LucidePencil, LucidePlus,
    LucideRefreshCw, LucideSearch, LucideTrash2, LucideUpload, LucideUsers, LucideX,
  ],
  templateUrl: './productos.html',
  styleUrl: './productos.css',
})
export class Productos implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly companiesService = inject(CompaniesService);
  private readonly productsService = inject(ProductsService);
  private readonly mediaService = inject(MediaService);
  private readonly fb = inject(FormBuilder);

  protected readonly companies = signal<CompanyChoice[]>([]);
  protected readonly selectedCompanyId = signal<number | null>(null);
  protected readonly products = signal<TourismProduct[]>([]);
  protected readonly types = signal<ProductType[]>([]);
  protected readonly currencies = signal<Currency[]>([]);
  protected readonly cities = signal<City[]>([]);
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly showForm = signal(false);
  protected readonly editingProduct = signal<TourismProduct | null>(null);
  protected readonly searchTerm = signal('');
  protected readonly statusFilter = signal<StatusFilter>('TODOS');
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly formError = signal<string | null>(null);
  protected readonly successMessage = signal<string | null>(null);

  // Cloudinary / Media upload states
  protected readonly currentImageUrl = signal<string>('');
  protected readonly uploadingImage = signal(false);
  protected readonly imageUploadError = signal<string | null>(null);
  protected readonly showManualUrl = signal(false);
  protected readonly isDragOver = signal(false);

  protected readonly isSuperAdmin = computed(() => this.auth.session()?.user.roles.includes('SUPER_ADMIN') ?? false);
  protected readonly canManage = computed(() => {
    const user = this.auth.session()?.user;
    return !!user && (user.roles.includes('SUPER_ADMIN') || user.permisos.includes('PRODUCTOS_GESTIONAR'));
  });
  protected readonly selectedCompany = computed(() => this.companies().find((item) => item.id === this.selectedCompanyId()));
  protected readonly publishedCount = computed(() => this.products().filter((item) => item.estado === 'PUBLICADO').length);
  protected readonly filteredProducts = computed(() => {
    const query = this.searchTerm().trim().toLocaleLowerCase('es');
    const status = this.statusFilter();
    return this.products().filter((product) =>
      (status === 'TODOS' || product.estado === status) &&
      [product.nombre, product.tipo, product.ciudad, product.localidad, product.codigo].join(' ').toLocaleLowerCase('es').includes(query),
    );
  });

  protected readonly productForm = this.fb.nonNullable.group({
    nombre: ['', Validators.required],
    tipo_codigo: ['', Validators.required],
    ciudad_id: [0, [Validators.required, Validators.min(1)]],
    localidad: [''],
    moneda_codigo: ['BOB', Validators.required],
    precio_base: [0, [Validators.required, Validators.min(0)]],
    capacidad_maxima: [1, [Validators.required, Validators.min(1)]],
    descripcion: [''],
    imagen_url: [''],
    estado: ['BORRADOR' as ProductStatus, Validators.required],
  });

  ngOnInit(): void {
    const sessionCompanies = this.auth.session()?.user.tenants.map((item) => ({ id: item.id, name: item.name })) ?? [];
    forkJoin({ types: this.productsService.listTypes(), currencies: this.productsService.listCurrencies(), cities: this.companiesService.listCities() }).subscribe({
      next: ({ types, currencies, cities }) => {
        this.types.set(types); this.currencies.set(currencies); this.cities.set(cities);
        if (this.isSuperAdmin()) {
          this.companiesService.list('', 'ACTIVO').subscribe({
            next: (companies) => this.initializeCompanies(companies.map((item) => ({ id: item.id, name: item.nombre_comercial }))),
            error: () => this.failLoading('No fue posible cargar las empresas.'),
          });
        } else this.initializeCompanies(sessionCompanies);
      },
      error: () => this.failLoading('No fue posible cargar los catálogos del producto. Ejecuta las migraciones pendientes.'),
    });
  }

  private initializeCompanies(companies: CompanyChoice[]): void {
    this.companies.set(companies);
    if (!companies.length) return this.failLoading('Tu cuenta no tiene una empresa activa asignada.');
    this.selectedCompanyId.set(companies[0].id);
    this.loadProducts();
  }

  private failLoading(message: string): void { this.loading.set(false); this.errorMessage.set(message); }

  protected changeCompany(event: Event): void {
    this.selectedCompanyId.set(Number((event.target as HTMLSelectElement).value));
    this.cancelForm(); this.loadProducts();
  }

  protected loadProducts(): void {
    const companyId = this.selectedCompanyId();
    if (!companyId) return;
    this.loading.set(true); this.errorMessage.set(null);
    this.productsService.listCompanyProducts(companyId).subscribe({
      next: (products) => { this.products.set(products); this.loading.set(false); },
      error: (error: HttpErrorResponse) => { this.loading.set(false); this.errorMessage.set(this.apiMessage(error, 'No fue posible cargar el catálogo.')); },
    });
  }

  protected startCreate(): void {
    this.editingProduct.set(null);
    this.currentImageUrl.set('');
    this.imageUploadError.set(null);
    this.showManualUrl.set(false);
    this.productForm.reset({
      tipo_codigo: this.types()[0]?.codigo ?? '',
      ciudad_id: this.cities()[0]?.id ?? 0,
      moneda_codigo: this.currencies()[0]?.codigo ?? 'BOB',
      precio_base: 0,
      capacidad_maxima: 1,
      estado: 'BORRADOR',
    });
    this.formError.set(null);
    this.showForm.set(true);
  }

  protected startEdit(product: TourismProduct): void {
    this.editingProduct.set(product);
    this.currentImageUrl.set(product.imagen_url ?? '');
    this.imageUploadError.set(null);
    this.showManualUrl.set(!!product.imagen_url && !this.isCloudinaryUrl(product.imagen_url));
    this.productForm.setValue({
      nombre: product.nombre,
      tipo_codigo: product.tipo_codigo,
      ciudad_id: product.ciudad_id,
      localidad: product.localidad ?? '',
      moneda_codigo: product.moneda_codigo,
      precio_base: Number(product.precio_base),
      capacidad_maxima: product.capacidad_maxima,
      descripcion: product.descripcion ?? '',
      imagen_url: product.imagen_url ?? '',
      estado: product.estado,
    });
    this.formError.set(null);
    this.showForm.set(true);
  }

  protected cancelForm(): void {
    this.showForm.set(false);
    this.editingProduct.set(null);
    this.currentImageUrl.set('');
    this.imageUploadError.set(null);
    this.productForm.reset();
  }

  protected submitProduct(): void {
    const companyId = this.selectedCompanyId();
    if (!companyId || this.productForm.invalid) { this.productForm.markAllAsTouched(); return; }
    const raw = this.productForm.getRawValue();
    const payload = { ...raw, nombre: raw.nombre.trim(), localidad: raw.localidad.trim() || undefined, descripcion: raw.descripcion.trim() || undefined, imagen_url: raw.imagen_url.trim() || undefined };
    const editing = this.editingProduct();
    this.saving.set(true); this.formError.set(null);
    const request = editing ? this.productsService.update(companyId, editing.id, payload) : this.productsService.create(companyId, payload);
    request.subscribe({
      next: (product) => {
        this.products.update((items) => editing ? items.map((item) => item.id === product.id ? product : item) : [product, ...items]);
        this.saving.set(false); this.successMessage.set(editing ? 'Publicación actualizada.' : 'Producto creado correctamente.'); this.cancelForm();
      },
      error: (error: HttpErrorResponse) => { this.saving.set(false); this.formError.set(this.apiMessage(error, 'No fue posible guardar el producto.')); },
    });
  }

  protected togglePublication(product: TourismProduct): void {
    const companyId = this.selectedCompanyId();
    if (!companyId) return;
    const estado: ProductStatus = product.estado === 'PUBLICADO' ? 'BORRADOR' : 'PUBLICADO';
    this.productsService.update(companyId, product.id, { estado }).subscribe({
      next: (updated) => this.products.update((items) => items.map((item) => item.id === updated.id ? updated : item)),
      error: (error: HttpErrorResponse) => this.errorMessage.set(this.apiMessage(error, 'No fue posible cambiar la publicación.')),
    });
  }

  protected deactivate(product: TourismProduct): void {
    const companyId = this.selectedCompanyId();
    if (!companyId || !confirm(`¿Desactivar “${product.nombre}”?`)) return;
    this.productsService.deactivate(companyId, product.id).subscribe({
      next: (updated) => this.products.update((items) => items.map((item) => item.id === updated.id ? updated : item)),
      error: (error: HttpErrorResponse) => this.errorMessage.set(this.apiMessage(error, 'No fue posible desactivar el producto.')),
    });
  }

  protected updateSearch(event: Event): void { this.searchTerm.set((event.target as HTMLInputElement).value); }
  protected updateStatus(event: Event): void { this.statusFilter.set((event.target as HTMLSelectElement).value as StatusFilter); }

  protected imageError(event: Event): void {
    (event.target as HTMLImageElement).style.display = 'none';
  }

  // --- Cloudinary / Image Upload Actions ---
  protected onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    this.uploadFile(file);
    input.value = '';
  }

  protected onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver.set(true);
  }

  protected onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver.set(false);
  }

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver.set(false);
    if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
      const file = event.dataTransfer.files[0];
      this.uploadFile(file);
    }
  }

  private uploadFile(file: File): void {
    this.imageUploadError.set(null);

    const validTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/avif', 'image/gif'];
    if (!validTypes.includes(file.type)) {
      this.imageUploadError.set('Formato no admitido. Selecciona un archivo JPG, PNG, WEBP o AVIF.');
      return;
    }

    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      this.imageUploadError.set('La imagen supera el límite de 10 MB.');
      return;
    }

    this.uploadingImage.set(true);
    this.mediaService.uploadImage(file, 'productos').subscribe({
      next: (res) => {
        this.productForm.patchValue({ imagen_url: res.url });
        this.currentImageUrl.set(res.url);
        this.uploadingImage.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.uploadingImage.set(false);
        this.imageUploadError.set(this.apiMessage(error, 'No fue posible subir la imagen a Cloudinary.'));
      },
    });
  }

  protected removeImage(): void {
    this.productForm.patchValue({ imagen_url: '' });
    this.currentImageUrl.set('');
    this.imageUploadError.set(null);
  }

  protected toggleManualUrl(): void {
    this.showManualUrl.update((v) => !v);
  }

  protected onManualUrlInput(event: Event): void {
    const val = (event.target as HTMLInputElement).value;
    this.currentImageUrl.set(val);
  }

  protected isCloudinaryUrl(url: string): boolean {
    return url.includes('cloudinary.com') || url.includes('res.cloudinary');
  }

  private apiMessage(error: HttpErrorResponse, fallback: string): string {
    const details = error.error?.error?.details;
    if (details && typeof details === 'object') {
      const first = Object.values(details).flat()[0]; if (typeof first === 'string') return first;
    }
    return error.error?.error?.message ?? fallback;
  }
}
