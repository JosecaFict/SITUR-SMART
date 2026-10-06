# Credenciales de demostración — SITUR-SMART

> Archivo generado por `python manage.py seed_bolivia --credenciales`. No editar a mano:
> los datos viven en `backend/apps/catalog/seed/bolivia.py`.

**Contraseña de todas las cuentas: `Admin123*`**

Son datos de prueba. Los nombres de las empresas son reales; precios, habitaciones,
servicios y coordenadas son aproximados. Las imágenes se cargan a mano desde el panel.

La cuenta del **SuperAdmin** no está aquí: se crea con `python manage.py createsituradmin`.

## Resumen

- 18 empresas, 53 cuentas.
- 8 hoteles con 27 tipos de habitación.
- 37 productos más (restaurantes, tours, experiencias, atracciones y paquetes).
- Una empresa suspendida (Red Cap Walking Tours) y una pendiente de activación (Tupiza Tours).

## Cómo cargar los datos

```powershell
cd backend
python manage.py createsituradmin        # solo si todavía no existe un SuperAdmin
python manage.py seed_bolivia            # carga todo; lo que ya existe se omite
python manage.py seed_bolivia --reset    # borra lo que creó el seed y lo vuelve a cargar
```

Sin acceso a `manage.py` (por ejemplo, la base de Railway): abrir
`backend/database/seed_bolivia.sql` en el Query Tool de pgAdmin y ejecutarlo. Hace lo mismo
y se puede ejecutar más de una vez.

## Empresas

| Empresa | Perfil | Plan | Ciudad | Estado |
|---|---|---|---|---|
| Hotel Cortez | Solo hotel | Básico | Santa Cruz de la Sierra | Activa |
| Hotel La Cúpula | Solo hotel | Básico | Copacabana | Activa |
| Hoteles Rosario | Cadena: dos hoteles y restaurante | Pro | La Paz / Copacabana | Activa |
| Hotel Palacio de Sal | Hotel con restaurante | Básico | Uyuni | Activa |
| Parador Santa María La Real | Hotel con restaurante | Básico | Sucre | Activa |
| SczTourBo | Agencia completa (hotel en convenio, tours y paquetes) | Max | Santa Cruz de la Sierra / Samaipata | Activa |
| Gustu | Solo restaurante | Básico | La Paz | Activa |
| Paceña La Salteña | Cadena gastronómica | Pro | La Paz | Activa |
| Casa del Camba | Solo restaurante | Básico | Santa Cruz de la Sierra | Activa |
| Casa de Campo | Solo restaurante | Básico | Cochabamba | Activa |
| Gravity Bolivia | Tours y experiencias de aventura | Pro | La Paz | Activa |
| Red Cap Walking Tours | Tours a pie (empresa suspendida) | Básico | La Paz | Suspendida |
| Red Planet Expedition | Tours por el salar y paquetes | Pro | Uyuni | Activa |
| Madidi Jungle Ecolodge | Ecolodge con tours de selva | Pro | Rurrenabaque | Activa |
| Bodegas Kohlberg | Experiencias de vino y singani | Básico | Tarija | Activa |
| Parque Cretácico | Atracción | Básico | Sucre | Activa |
| Casa Nacional de Moneda | Atracción | Básico | Potosí | Activa |
| Tupiza Tours | Autorregistro pendiente de activación | Básico | Tupiza | Pendiente de activación por el SuperAdmin |

### Hotel Cortez

- **Perfil:** Solo hotel
- **Plan:** Básico
- **Estado:** Activa
- **Publica:** 1 hotel, 4 tipos de habitación

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@hotelcortez.com.bo` |
| Recepcionista | `empleado1@hotelcortez.com.bo` |
| Empleado | `empleado2@hotelcortez.com.bo` |

### Hotel La Cúpula

- **Perfil:** Solo hotel
- **Plan:** Básico
- **Estado:** Activa
- **Publica:** 1 hotel, 3 tipos de habitación

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@hotelcupula.com.bo` |
| Recepcionista | `empleado1@hotelcupula.com.bo` |

### Hoteles Rosario

- **Perfil:** Cadena: dos hoteles y restaurante
- **Plan:** Pro
- **Estado:** Activa
- **Publica:** 2 hoteles, 7 tipos de habitación, 1 restaurante

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@hotelesrosario.com.bo` |
| Recepcionista | `empleado1@hotelesrosario.com.bo` |
| Recepcionista | `empleado2@hotelesrosario.com.bo` |
| Empleado | `empleado3@hotelesrosario.com.bo` |

### Hotel Palacio de Sal

- **Perfil:** Hotel con restaurante
- **Plan:** Básico
- **Estado:** Activa
- **Publica:** 1 hotel, 3 tipos de habitación, 1 restaurante

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@palaciodesal.com.bo` |
| Recepcionista | `empleado1@palaciodesal.com.bo` |
| Empleado | `empleado2@palaciodesal.com.bo` |

### Parador Santa María La Real

- **Perfil:** Hotel con restaurante
- **Plan:** Básico
- **Estado:** Activa
- **Publica:** 1 hotel, 3 tipos de habitación, 1 restaurante

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@paradorsantamaria.com.bo` |
| Recepcionista | `empleado1@paradorsantamaria.com.bo` |

### SczTourBo

- **Perfil:** Agencia completa (hotel en convenio, tours y paquetes)
- **Plan:** Max
- **Estado:** Activa
- **Publica:** 1 hotel, 5 tipos de habitación, 3 tours, 2 experiencias, 2 paquetes

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@scztourbo.com.bo` |
| Encargado de catálogo | `empleado1@scztourbo.com.bo` |
| Empleado | `empleado2@scztourbo.com.bo` |
| Guía turístico | `guia1@scztourbo.com.bo` |
| Guía turístico | `guia2@scztourbo.com.bo` |

### Gustu

- **Perfil:** Solo restaurante
- **Plan:** Básico
- **Estado:** Activa
- **Publica:** 1 restaurante

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@gustu.com.bo` |
| Cajero | `empleado1@gustu.com.bo` |

### Paceña La Salteña

- **Perfil:** Cadena gastronómica
- **Plan:** Pro
- **Estado:** Activa
- **Publica:** 4 restaurantes

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@pacenalasaltena.com.bo` |
| Cajero | `empleado1@pacenalasaltena.com.bo` |
| Cajero | `empleado2@pacenalasaltena.com.bo` |

### Casa del Camba

- **Perfil:** Solo restaurante
- **Plan:** Básico
- **Estado:** Activa
- **Publica:** 1 restaurante

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@casadelcamba.com.bo` |
| Cajero | `empleado1@casadelcamba.com.bo` |

### Casa de Campo

- **Perfil:** Solo restaurante
- **Plan:** Básico
- **Estado:** Activa
- **Publica:** 1 restaurante

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@casadecampo.com.bo` |
| Cajero | `empleado1@casadecampo.com.bo` |

### Gravity Bolivia

- **Perfil:** Tours y experiencias de aventura
- **Plan:** Pro
- **Estado:** Activa
- **Publica:** 3 tours, 1 experiencia

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@gravitybolivia.com.bo` |
| Encargado de catálogo | `empleado1@gravitybolivia.com.bo` |
| Guía turístico | `guia1@gravitybolivia.com.bo` |
| Guía turístico | `guia2@gravitybolivia.com.bo` |

### Red Cap Walking Tours

- **Perfil:** Tours a pie (empresa suspendida)
- **Plan:** Básico
- **Estado:** Suspendida (su oferta no aparece en el Marketplace)
- **Publica:** 2 tours, 1 experiencia

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@redcapwalkingtours.com.bo` |
| Guía turístico | `guia1@redcapwalkingtours.com.bo` |
| Guía turístico | `guia2@redcapwalkingtours.com.bo` |

### Red Planet Expedition

- **Perfil:** Tours por el salar y paquetes
- **Plan:** Pro
- **Estado:** Activa
- **Publica:** 3 tours, 1 experiencia, 1 paquete

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@redplanetexpedition.com.bo` |
| Empleado | `empleado1@redplanetexpedition.com.bo` |
| Guía turístico | `guia1@redplanetexpedition.com.bo` |
| Guía turístico | `guia2@redplanetexpedition.com.bo` |

### Madidi Jungle Ecolodge

- **Perfil:** Ecolodge con tours de selva
- **Plan:** Pro
- **Estado:** Activa
- **Publica:** 1 hotel, 2 tipos de habitación, 2 tours, 1 experiencia

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@madidijungle.com.bo` |
| Recepcionista | `empleado1@madidijungle.com.bo` |
| Guía turístico | `guia1@madidijungle.com.bo` |

### Bodegas Kohlberg

- **Perfil:** Experiencias de vino y singani
- **Plan:** Básico
- **Estado:** Activa
- **Publica:** 2 experiencias

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@kohlberg.com.bo` |
| Empleado | `empleado1@kohlberg.com.bo` |

### Parque Cretácico

- **Perfil:** Atracción
- **Plan:** Básico
- **Estado:** Activa
- **Publica:** 1 experiencia, 1 atracción

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@parquecretacico.com.bo` |
| Empleado | `empleado1@parquecretacico.com.bo` |

### Casa Nacional de Moneda

- **Perfil:** Atracción
- **Plan:** Básico
- **Estado:** Activa
- **Publica:** 1 atracción

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@casadelamoneda.com.bo` |
| Empleado | `empleado1@casadelamoneda.com.bo` |

### Tupiza Tours

- **Perfil:** Autorregistro pendiente de activación
- **Plan:** Básico
- **Estado:** Pendiente de activación por el SuperAdmin
- **Publica:** Sin oferta cargada todavía

| Rol | Email |
|---|---|
| Propietario | `jefeadmin@tupizatours.com.bo` |

## Turistas

Cuentas con rol CLIENTE, sin empresa. Sirven para probar el Marketplace y el asistente.

| Nombre | Email |
|---|---|
| Lucía Fernández Rojas | `turista1@situr.com.bo` |
| Martín Gutiérrez Vaca | `turista2@situr.com.bo` |
| Camila Mamani Quispe | `turista3@situr.com.bo` |
| Diego Torrez Salvatierra | `turista4@situr.com.bo` |

## Roles personalizados

Cada empresa que los usa los crea dentro de su tenant.

| Rol | Permisos |
|---|---|
| Recepcionista | PRODUCTOS_LEER, DISPONIBILIDAD_GESTIONAR, RESERVAS_LEER, RESERVAS_GESTIONAR |
| Encargado de catálogo | PRODUCTOS_LEER, PRODUCTOS_GESTIONAR, DISPONIBILIDAD_GESTIONAR, REPORTES_TENANT |
| Cajero | PRODUCTOS_LEER, RESERVAS_LEER, RESERVAS_GESTIONAR |
