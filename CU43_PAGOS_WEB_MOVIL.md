# CU43 — Gestión de pagos, cancelaciones y reembolsos

Estado del documento: **Fase 0 aprobada**

Alcance: backend compartido, web Angular y aplicación Flutter

Principio rector: web y móvil muestran resultados; las reglas financieras se
calculan y ejecutan exclusivamente en el backend.

## 1. Objetivo

Cerrar el ciclo financiero de una reserva desde la cotización hasta el cobro,
la cancelación, el reembolso, el comprobante, la conciliación y el reporte, con
el mismo comportamiento en web y móvil.

## 2. Actores y alcance

| Actor | Capacidades financieras |
|---|---|
| Turista | Pagar, consultar sus pagos, descargar comprobantes, cotizar una cancelación y solicitarla |
| Dueño de empresa | Consultar movimientos de su empresa, registrar pagos manuales, cancelar servicios y gestionar reembolsos autorizados |
| Empleado autorizado | Las mismas operaciones empresariales que permitan sus permisos explícitos |
| Superadministrador | Supervisión global, conciliación, resolución de incidencias y reportes de todas las empresas |
| Stripe | Cobro, devolución y notificación mediante webhooks firmados |
| Proceso programado | Expiración, conciliación y detección de diferencias |

Flutter se cierra primero para el turista. Las operaciones financieras de la
empresa permanecen en la web hasta que exista un requisito explícito para un
módulo móvil empresarial.

## 3. Política inicial aprobada

| Anticipación respecto al inicio del servicio | Penalización | Reembolso |
|---|---:|---:|
| 7 días o más | 0 % | 100 % |
| Entre 3 y 6 días | 25 % | 75 % |
| Entre 1 y 2 días | 50 % | 50 % |
| Mismo día | 100 % | 0 % |
| No-show | 100 % | 0 % |
| Cancelación atribuible a la empresa | 0 % | 100 % |
| Fuerza mayor aprobada por la empresa o plataforma | 0 % | 100 % |
| Cobro duplicado confirmado | 0 % | 100 % del duplicado |

### 3.1 Reglas de vigencia

1. Cada producto publicado debe tener una política asociada.
2. Se creará una política inicial para cada empresa y se asociará a sus
   productos publicados antes de hacer obligatoria la validación.
3. La empresa podrá definir políticas diferentes en una fase posterior, pero
   no podrá alterar las condiciones de reservas ya creadas.
4. Al reservar se congela una copia de la política aceptada, sus reglas, su
   identificador y la fecha de aceptación.
5. La cotización de cancelación usa la copia aceptada, no la versión vigente
   del producto.
6. Los días se calculan en la zona horaria `America/La_Paz`, comparando la
   fecha local de cancelación con el primer día del servicio.

## 4. Decisiones financieras

### 4.1 Precio y moneda

- El pago guarda precio original, descuento, total final y moneda.
- Reportes y reembolsos usan el monto congelado; nunca recalculan el catálogo.
- No se convierte moneda durante un reembolso.
- La suma de reembolsos completados o en proceso nunca puede superar el pago
  aprobado.

### 4.2 Cancelación y cupo

- Una reserva no pagada se cancela inmediatamente y libera su bloqueo.
- Una reserva pagada conserva el cupo hasta que la solicitud de cancelación y
  el reembolso queden registrados atómicamente.
- Si el reembolso externo falla, la operación queda pendiente de revisión y no
  se repite sin la misma clave de idempotencia.
- La cancelación de una salida por la empresa devuelve el 100 % y notifica a
  todos los turistas afectados.
- El check-in y una reserva completada impiden una cancelación ordinaria.

### 4.3 Reembolsos

- Se admiten reembolsos totales y parciales.
- Todo reembolso referencia un pago aprobado.
- Stripe confirma el resultado mediante webhook firmado.
- Un webhook repetido no duplica movimientos ni libera dos veces el cupo.
- Una devolución manual solo puede registrarse con permiso, motivo, referencia
  y evidencia suficiente.

### 4.4 Pagos manuales

Métodos permitidos: efectivo, QR externo y transferencia. Pueden registrarlos
el dueño, un empleado con permiso financiero o el superadministrador. Deben
guardar empresa, reserva, monto, moneda, referencia, fecha, usuario que lo
registró y comprobante opcional. No se permite editar un pago confirmado; una
corrección se realiza con anulación o movimiento compensatorio y bitácora.

### 4.5 Factura o recibo

Datos mínimos: NIT o documento, razón social o nombre fiscal y correo. El dato
queda asociado al documento emitido sin reemplazar los datos históricos si el
turista modifica después su perfil.

## 5. Estados oficiales

### 5.1 Pago

| Estado | Significado |
|---|---|
| `PENDIENTE` | Sesión creada, sin confirmación de cobro |
| `APROBADO` | Cobro confirmado |
| `RECHAZADO` | El proveedor rechazó el cobro |
| `ANULADO` | La sesión expiró o se cerró sin cobrar |

Un pago aprobado no cambia a “reembolsado”. Sus devoluciones se representan
como movimientos independientes para conservar el historial.

### 5.2 Reembolso

| Estado | Significado |
|---|---|
| `SOLICITADO` | Registrado localmente y todavía no enviado o confirmado |
| `PROCESANDO` | Aceptado por el proveedor, pendiente de confirmación final |
| `COMPLETADO` | Confirmado por Stripe o por conciliación |
| `FALLIDO` | Rechazado o imposible de ejecutar |
| `CANCELADO` | Solicitud anulada antes de procesarse |

### 5.3 Conciliación

| Estado | Significado |
|---|---|
| `COINCIDE` | Base y Stripe tienen el mismo resultado |
| `DIFERENCIA` | Monto, moneda o estado no coinciden |
| `SOLO_LOCAL` | Existe en SITUR-SMART y no en Stripe |
| `SOLO_PROVEEDOR` | Existe en Stripe y no en SITUR-SMART |
| `RESUELTA` | Un usuario autorizado documentó la corrección |

## 6. Objetos BCE

### 6.1 Boundary

**Web turista:** reserva, resultado de pago, Mis pagos, detalle de pago,
cotización de cancelación, seguimiento de reembolso y facturación.

**Web empresa:** pagos de la empresa, filtros y totales, pago manual,
cancelación de salida, progreso de devoluciones y exportación.

**Flutter turista:** hoja de reserva, retorno por deep link, Mis pagos, detalle
de pago, cancelación, seguimiento y comprobantes.

**Externos:** Stripe Checkout, Stripe Refund API, webhook firmado, correo y
notificaciones push.

### 6.2 Control

- `CotizarReservaControl`
- `IniciarPagoControl`
- `ConfirmarPagoControl`
- `ConsultarPagosControl`
- `CotizarCancelacionControl`
- `CancelarReservaControl`
- `SolicitarReembolsoControl`
- `ConfirmarReembolsoControl`
- `RegistrarPagoManualControl`
- `CancelarServicioEmpresaControl`
- `ConciliarPagosControl`
- `GenerarComprobanteControl`
- `GenerarReporteFinancieroControl`

### 6.3 Entity

- `Reserva`
- `Orden`
- `Pago`
- `Reembolso`
- `Cancelacion`
- `PoliticaCancelacion`
- `ReglaPenalizacion`
- `AceptacionPolitica`
- `Disponibilidad`
- `DatosFacturacion`
- `Comprobante`
- `Conciliacion`
- `Bitacora`

## 7. Contrato API objetivo

Los nombres definitivos se mantienen compatibles con las rutas existentes. Se
agregan rutas; no se rompe `pagar`, `cancelar`, comprobante ni webhook.

### 7.1 Turista — compartido por Angular y Flutter

| Método y ruta | Propósito |
|---|---|
| `GET /me/pagos/` | Historial paginado y filtrable del turista |
| `GET /me/pagos/{id}/` | Pago, reserva, comprobante y reembolsos relacionados |
| `GET /me/reservas/{id}/cancelacion/cotizacion/` | Simulación autoritativa sin cambiar estado |
| `POST /me/reservas/{id}/cancelacion/` | Confirma cancelación y crea el reembolso idempotente |
| `GET /me/reembolsos/{id}/` | Estado actualizado de la devolución |
| `GET /me/reservas/{id}/comprobante/` | Enlace firmado al comprobante |
| `PUT /me/datos-facturacion/` | Guarda datos reutilizables del turista |
| `POST /me/pagos/{id}/documento-fiscal/` | Solicita recibo o factura |

### 7.2 Empresa — web

| Método y ruta | Propósito |
|---|---|
| `GET /empresa/pagos/` | Movimientos del tenant actual |
| `GET /empresa/pagos/resumen/` | Cobrado, pendiente, reembolsado y neto |
| `POST /empresa/pagos/manuales/` | Registra un cobro fuera de Stripe |
| `POST /empresa/reservas/{id}/cancelacion/` | Cancelación empresarial con devolución total |
| `POST /empresa/salidas/{id}/cancelacion/` | Cancela una salida y procesa reservas afectadas |

### 7.3 Plataforma — superadministrador

| Método y ruta | Propósito |
|---|---|
| `GET /admin/pagos/` | Consulta global con filtros por empresa |
| `GET /admin/conciliaciones/` | Diferencias detectadas |
| `POST /admin/conciliaciones/{id}/resolver/` | Registra la resolución y su evidencia |

Todas las operaciones mutables aceptan `Idempotency-Key` cuando puedan
repetirse por doble clic, mala conexión, webhook o tarea programada.

## 8. Trabajo paralelo web y móvil

Web y Flutter avanzan simultáneamente solo después de estabilizar cada contrato
backend. Para cada bloque se sigue esta secuencia:

1. Entidad y migración.
2. Control y reglas de negocio.
3. Endpoint y esquema OpenAPI.
4. Pruebas backend.
5. Modelo/servicio Angular y Dart en paralelo.
6. Boundary web y móvil en paralelo.
7. Pruebas de contrato y aceptación cruzada.

| Bloque | Backend | Web | Flutter |
|---|---|---|---|
| Política antes de pagar | Congelar y exponer política | Resumen y aceptación | Resumen y aceptación |
| Mis pagos | Listado y detalle | Pantallas web | Pantallas móviles |
| Cancelación | Cotizar, confirmar y reembolsar | Modal y seguimiento | Flujo y seguimiento |
| Comprobantes | PDF/factura y enlaces | Descargar | Abrir/descargar |
| Empresa | Pagos, manuales y cancelaciones | Panel administrativo | Fuera del primer alcance |
| Reportes | Agregaciones CU47 | PDF/Excel | Fuera del alcance administrativo |

## 9. Fases de ejecución

### Fase 0 — Reglas y contrato

**Terminada con este documento.**

### Fase 1 — Núcleo backend

1. Sembrar y asociar la política inicial sin romper productos publicados.
2. Congelar política y precio al reservar.
3. Crear `Reembolso` y restricciones de integridad.
4. Ejecutar reembolsos Stripe con idempotencia.
5. Procesar webhook y conciliación de reembolsos.
6. Liberar cupo, notificar y auditar de forma consistente.

### Fase 2 — Turista web y móvil en paralelo

1. Política antes de pagar.
2. Mis pagos y detalle.
3. Cancelación cotizada.
4. Estado de reembolso.
5. Comprobante y datos fiscales.

### Fase 3 — Administración web

1. Movimientos y resumen por empresa.
2. Pago manual.
3. Cancelación empresarial individual y masiva.
4. Supervisión global del superadministrador.

### Fase 4 — Robustez e integración

1. Conciliación diaria.
2. Orden completa de CU39.
3. Reportes financieros CU47.
4. Pruebas de carga, duplicados, permisos y recuperación.

## 10. Criterios de aceptación

- Web y móvil obtienen el mismo precio, penalización y reembolso.
- Ningún cliente calcula importes localmente.
- Un doble clic no duplica reserva, cobro, cancelación ni devolución.
- Un webhook repetido es inocuo.
- El turista solo consulta sus movimientos.
- Una empresa solo consulta y administra sus movimientos.
- El superadministrador puede supervisar todas las empresas.
- El pago conserva precio, descuento, total, moneda y política aceptada.
- Todo reembolso conserva causa, actor, fechas, importes y referencia externa.
- La suma reembolsada nunca supera el pago aprobado.
- Cancelar por causa empresarial devuelve el 100 %.
- El cupo se libera una sola vez.
- Pago, cancelación, reembolso y operación manual quedan en bitácora.
- PDF y Excel se generan desde movimientos confirmados, no desde precios de
  catálogo ni condiciones comerciales de una suscripción.

## 11. Definición de terminado de CU43

CU43 termina cuando el turista completa el ciclo en web y Flutter; las empresas
gestionan cobros, pagos manuales y cancelaciones desde web; Stripe y la base se
concilian; los permisos y tenants están aislados; y todas las rutas críticas
tienen pruebas automatizadas de éxito, error, reintento e idempotencia.
