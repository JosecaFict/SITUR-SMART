# CU51 — Promociones comerciales, fase 1

Contrato backend; Angular consume estas APIs en la fase 2. Flutter no se modificó. CU39 conserva sus
modelos, permisos, endpoints y paquetes privados. No se modificaron `.env`,
credenciales, configuración de PostgreSQL ni código de `apps/payments/`.

## Modalidades

**EXISTENTE (A).** Descuento porcentual sobre un producto publicado de tipo
`TOUR`, `EXPERIENCIA`, `ATRACCION`, `RESTAURANTE` o `PAQUETE`, de la propia
empresa, con precio positivo. `HOTEL` no se reserva directamente.
`HABITACION` queda excluida: su reserva multiplica el precio por noches,
mientras el snapshot promocional actual calcula importes por cantidad de unidades.
No se cambia `precio_base`.
La cotización y la reserva aplican el mismo cálculo. Una reserva promocional
guarda los importes acordados en `reserva_promocion`.

**COMBINADO (B).** Oferta comercial independiente, con referencias a servicios
propios y sus fechas, cantidades, huéspedes y salidas. No crea un producto
`PAQUETE` artificial ni convierte un paquete privado de CU39.
Admite HABITACION, TOUR, EXPERIENCIA, ATRACCION y RESTAURANTE.
HOTEL no se reserva directamente; se elige una habitación.
No admite PAQUETE como componente, evitando descuentos anidados.

**B no se puede reservar todavía.** Devuelve `admite_reservas: false` y
`reservable: false`, aunque todos los componentes tengan cupos. Falta un
checkout conjunto con adquisición atómica de inventario de todos los servicios,
una relación explícita entre oferta, orden y reservas, y su coordinación con
CU43. Enviar su `promocion_id` al endpoint de reservas se rechaza. No hay reservas
parciales ni pagos simulados en la implementación.

## Entidades y migraciones

| Modelo | Tabla | Función |
| --- | --- | --- |
| `Promotion` | `promocion_comercial` | Empresa, modalidad, producto opcional, nombre, descripción, porcentaje, vigencia, estado y creador |
| `PromotionComponent` | `promocion_componente` | Producto, fecha de servicio, salida, cantidades y precios de referencia |
| `BookingPromotionSnapshot` | `reserva_promocion` | Descuento e importes inmutables desde el flujo de reserva |

Las tres tablas son `managed=True`. Las tablas históricas `managed=False`
conservan su esquema y sus scripts SQL.

- `promotions/0001_initial`: tablas, índices, claves foráneas y restricciones
  de porcentajes, fechas, cantidades y modalidades.
- `promotions/0002_postgres_integrity`: FK compuesta producto/empresa y exclusión
  GiST de vigencias superpuestas para promociones habilitadas de un mismo producto.
  Usa rangos nativos de PostgreSQL; no necesita instalar `btree_gist`.

No se creó un script SQL equivalente: estas tablas se administran exclusivamente
con migraciones Django, sin aplicar la misma operación por dos caminos.
La migración depende del estado existente de catalog, tenancy, bookings y accounts.

**Estado:** ambas migraciones se aplicaron y verificaron únicamente en bases de
prueba nuevas de PostgreSQL local. No se ejecutaron en Railway ni en la base
de desarrollo habitual. Deben aplicarse en el destino que se autorice antes de
usar las APIs de esta fase con esa base: las respuestas de productos y reservas
ya consultan las nuevas tablas. No se oculta una migración pendiente con precios
o descuentos de sustitución.

## Permisos y concurrencia

Las rutas empresariales requieren JWT y `X-Tenant-ID` numérico obligatorio.
Las lecturas usan `PRODUCTOS_LEER`; las escrituras, `PRODUCTOS_GESTIONAR`.
Se reutilizan membresía, estado de empresa y plan activo del proyecto.
Los IDs se buscan dentro de la empresa; componentes y promociones ajenos no
pueden editarse. El responsable y las operaciones quedan en la auditoría existente.

En A, edición, publicación y desactivación bloquean primero el producto y luego
la promoción. Checkout ya bloquea el producto y vuelve a cotizar dentro de la
transacción. La restricción de exclusión de PostgreSQL protege también contra
vigencias superpuestas al escribir fuera de la API.

En B, modificar componentes bloquea la promoción. Se rechazan duplicados del
mismo producto en días superpuestos y salidas cuyos horarios se solapan.
No se bloquea inventario al guardar, cotizar o publicar una oferta.

## Estados y precios

Estado administrativo: BORRADOR, HABILITADA o DESACTIVADA. Para una promoción
HABILITADA, el estado temporal se deriva en cada consulta:

- PROGRAMADA: `ahora < inicio`.
- VIGENTE: `inicio <= ahora < fin`.
- VENCIDA: `ahora >= fin`.

BORRADOR y DESACTIVADA conservan su estado administrativo. No se necesita cron.
Se usan datetimes conscientes de zona horaria y la zona configurada en Django
(`America/La_Paz`). Se recomienda enviar vigencias ISO 8601 con offset `-04:00`.
Las fechas de los servicios siguen siendo fechas locales, sin convertirlas en UTC.
Un período puede comenzar en el pasado si sigue vigente. Al guardar o publicar
debe tener `inicio < fin` y finalizar en el futuro. Dos períodos consecutivos
pueden compartir el instante de frontera.

El descuento se calcula con `Decimal` y `ROUND_HALF_UP`:

`precio_final = precio_original × (1 - porcentaje_descuento / 100)`

Se exige `0 < porcentaje < 100` y que el resultado redondeado sea positivo y
produzca un ahorro real. Se respeta la precisión de la moneda, hasta dos
decimales por compatibilidad con los importes existentes. Se rechazan precios
que excedan esa precisión o las columnas monetarias disponibles.

En A se redondea el precio unitario y después se multiplica por la cantidad,
coincidiendo exactamente con `BookingDetail.unit_price` y el importe enviado a
la pasarela. En B se suman los totales actuales de los componentes —incluyendo
noches y habitaciones— y se aplica una sola vez el descuento al conjunto.
No se aceptan precios calculados por el cliente como fuente de verdad.

Los precios de referencia de los componentes sirven para detectar cambios:
`precio_cambio` y `requiere_revalidacion`. La consulta siempre recalcula los
importes actuales; una referencia antigua no congela el precio de una nueva oferta.

## Disponibilidad y reservas

Se reutilizan `bookings.build_quote`, `bookings.availability` y `catalog.departures`.
Para B, un tour o experiencia con salidas requiere `salida_id` explícito. Cuando
solo existe disponibilidad diaria histórica, se exige un registro diario abierto;
no se inventan horarios ni cupos. Las habitaciones se validan por noche, cantidad
y capacidad de huéspedes. Productos retirados, planes restringidos, servicios
pasados, salidas cerradas y cupos insuficientes invalidan la oferta combinada.
No se publica un total parcial cuando falla un componente.

Para A, sin fecha, la respuesta devuelve `admite_reservas: true` si la oferta está
vigente y válida, pero `reservable: false`, `disponible: null` y
`requiere_fecha: true`. Con `?fecha=AAAA-MM-DD&cantidad=N` se comprueban los cupos
reales y se devuelve `cupos_restantes`, `disponible`, `reservable` y `cotizacion`.
Una consulta nunca aparta plazas. La reserva vuelve a validar dentro de su
transacción y conserva las protecciones existentes frente a sobreventa.

En B las cantidades y fechas están fijadas por sus componentes; el parámetro
`cantidad` de la consulta pública no multiplica una oferta combinada.

`POST /api/v1/me/reservas/cotizacion/` y `POST /api/v1/me/reservas/` aceptan el
campo opcional `promocion_id`, además del contrato previo. Para A:

1. Consultar producto/promoción y cotizar fecha y cantidad.
2. Enviar el `promocion_id` cotizado al reservar para detectar que se desactivó,
   venció o ya no corresponde al producto, sin caer silenciosamente al precio base.
3. La reserva almacena nombre, vigencia, porcentaje, moneda, precio original,
   precio final, cantidad, ahorro y totales en su snapshot.
4. El código de pagos recibe el total de la reserva mediante su integración actual.

Los clientes anteriores pueden omitir `promocion_id`: se aplica automáticamente
la promoción A vigente en ese momento. Como en el flujo existente, la cotización
es informativa; el precio base o porcentaje puede cambiar antes de crear la
reserva. La futura UI debe presentar la nueva cotización ante cambios y enviar
`promocion_id` cuando se eligió una oferta. No se introdujo una garantía de precio
por tiempo ni un token de cotización.

No se recalculan reservas ya creadas ni pagos pendientes/confirmados al editar o
vencer una promoción. Se conserva la idempotencia y la cancelación de reservas
pendientes. La política existente que rechaza cancelar reservas pagadas permanece
intacta. No se añadieron reembolsos.

## API

Todas las rutas llevan el prefijo `/api/v1/`.

| Método | Ruta | Resultado |
| --- | --- | --- |
| GET, POST | `promociones/` | Lista de la empresa / crear borrador |
| GET, PATCH | `promociones/{id}/` | Detalle / modificar campos editables |
| POST | `promociones/{id}/publicar/` | Habilitar; puede quedar PROGRAMADA |
| POST | `promociones/{id}/desactivar/` | Deshabilitar sin modificar reservas |
| GET | `promociones/productos-elegibles/?modalidad=EXISTENTE\|COMBINADO` | Catálogo propio elegible |
| POST | `promociones/cotizar/` | Calcular una propuesta sin persistirla |
| GET | `promociones/{id}/cotizacion/` | Recalcular condiciones y precios actuales |
| GET, POST | `promociones/{id}/componentes/` | Consultar / agregar componentes |
| PATCH, DELETE | `promociones/{id}/componentes/{componente_id}/` | Editar / quitar componente |
| GET | `marketplace/promociones/` | Promociones vigentes, válidas y habilitadas |
| GET | `marketplace/promociones/{id}/` | Detalle público y consulta de cupos para A |

Listas paginadas: `count`, `next`, `previous`, `results`; `page_size` por defecto
20, máximo 50. Los errores usan el manejador DRF existente. Las rutas y cuerpos
están incluidos en el esquema OpenAPI del proyecto.

Plantilla para crear A (sustituir marcadores por datos del catálogo real):

```text
POST /api/v1/promociones/
Authorization: Bearer <JWT>
X-Tenant-ID: <empresa>
{
  "modalidad": "EXISTENTE",
  "producto_id": <id_de_productos_elegibles>,
  "nombre": "<nombre de la oferta>",
  "descripcion": "<descripción opcional>",
  "porcentaje_descuento": "<porcentaje>",
  "inicio": "<fecha y hora ISO 8601 con offset>",
  "fin": "<fecha y hora ISO 8601 con offset>"
}
```

Para B: `modalidad: "COMBINADO"`, `producto_id: null` y `componentes` opcional
al crear. Cada componente recibe `producto_id`, `fecha_inicio`, `cantidad`;
`fecha_fin`/`huespedes` para habitación, `salida_id` para una salida horaria.
Se puede construir el borrador por etapas. Publicar requiere entre 2 y 20
componentes válidos de la misma empresa y moneda.

El PATCH de promoción permite `nombre`, `descripcion`, `porcentaje_descuento`,
`inicio` y `fin`. Modalidad y producto original son inmutables. Para cambiar
componentes de una oferta habilitada hay que desactivarla, editarla y publicarla
de nuevo. No hay borrado de promociones: se desactivan para conservar trazabilidad.

Los productos conservan sus campos actuales y añaden `promocion` con identificador,
modalidad, porcentaje, vigencia e importes, o `null` si no aplica.
La precarga de descuentos evita una consulta por tarjeta de producto.
Los filtros de precio existentes del marketplace siguen basándose en el precio
base; no se cambió su semántica en esta fase.

## Verificación y límites operativos

- 454 pruebas unitarias y 183 subpruebas aprobadas con `config.settings.test`.
- 81 pruebas de integración aprobadas con `config.settings.test_cu35_local`:
  `test_promociones.py`, `test_paquetes_personalizados.py`, `test_reservas.py`,
  `test_salidas.py`, `test_resenas.py` y `test_esquema.py`.
- Publicación concurrente: una promoción habilitada y un rechazo controlado.
- Reserva concurrente con descuento: una reserva y un rechazo por falta de cupo;
  importe de reserva, snapshot y Stripe simulado coincidentes.
- Verificados permisos, empresa/plan, monedas, fechas, redondeo, componentes,
  precios cambiantes, habitaciones, salidas y disponibilidad diaria heredada.
- Verificados snapshot, idempotencia tras desactivar, pago y cancelación pagada,
  ausencia de inventario/pagos al gestionar B y bloqueo de su checkout.
- `manage.py check`, `makemigrations --check --dry-run`, Ruff y OpenAPI válidos.
- Advertencias de pruebas existentes: directorio `staticfiles` ausente y claves
  de caché generadas por mocks; no son fallos de las pruebas.

Las ejecuciones usaron bases nuevas en `127.0.0.1:5432`:
`situr_smart_pruebas_cu51_20261031_a1`, `_a2` y `_a3` (verificación final).
Cada una se inicializó con los scripts SQL existentes y migraciones Django.
El fixture existente conserva estas bases al terminar; no se borró ninguna base.
Solo contienen datos de prueba locales. Las credenciales se obtuvieron del
mecanismo local existente y se pasaron por variables del proceso, sin persistirlas
en el repositorio. Stripe, correos y push utilizados en los casos nuevos se simularon.

La evaluación pública de B consulta dinámicamente todos sus componentes con el
motor existente. El listado filtra las ofertas inválidas antes de paginar, por lo
que su costo crece con la cantidad de ofertas candidatas. No introduce una caché
que pueda anunciar cupos antiguos; una optimización por lotes será necesaria si
el catálogo de promociones alcanza un volumen alto.

Se conservan `python manage.py runserver`, `npm start` y el script opcional
`start_cu35_local.ps1`. No se cambió el método de inicio ni se ejecutó una migración
remota. No hubo commit ni push.

## Archivos de esta fase

Nuevos:

- `apps/promotions/__init__.py`
- `apps/promotions/apps.py`
- `apps/promotions/models.py`
- `apps/promotions/pricing.py`
- `apps/promotions/services.py`
- `apps/promotions/serializers.py`
- `apps/promotions/views.py`
- `apps/promotions/urls.py`
- `apps/promotions/migrations/__init__.py`
- `apps/promotions/migrations/0001_initial.py`
- `apps/promotions/migrations/0002_postgres_integrity.py`
- `tests/integracion/test_promociones.py`
- `CU51_BACKEND.md`

Modificados, conservando los cambios previos de otros CU:

- `apps/bookings/services.py`: precio promocional y snapshot dentro de la reserva.
- `apps/bookings/serializers.py`: campo opcional de entrada y desglose de salida.
- `apps/bookings/views.py`: transmitir `promocion_id` al servicio.
- `apps/catalog/serializers.py`: resumen promocional y precarga en listas.
- `config/settings/base.py`: registrar la app, sin tocar DATABASES.
- `config/urls.py`: incluir las rutas de promociones.

## Próxima fase Angular

Pendientes la administración empresarial, el selector de componentes y salidas,
la vista pública de ofertas, etiquetas y precios promocionales, y la selección
de A en el formulario de reserva con `promocion_id`. La interfaz deberá distinguir
`admite_reservas`, `requiere_fecha`, `disponible` y `reservable`, presentar errores
de revalidación y no ofrecer checkout para B.
