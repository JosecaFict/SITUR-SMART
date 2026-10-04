export interface AdminCountry {
  id: number;
  codigo: string;
  nombre: string;
  activo: boolean;
  ciudades: number;
}

export interface AdminCity {
  id: number;
  nombre: string;
  pais_id: number;
  pais: string;
  latitud: string | null;
  longitud: string | null;
  zona_horaria: string | null;
  activo: boolean;
}

export interface CityPayload {
  nombre: string;
  pais_id: number;
  latitud: string | null;
  longitud: string | null;
  zona_horaria: string;
}
