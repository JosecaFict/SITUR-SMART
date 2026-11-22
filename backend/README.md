# Backend SITUR-SMART

API REST compartida para Angular y Flutter, desarrollada con Django, Django REST Framework y
PostgreSQL.

## Preparación local

1. Instalar Python 3.12 o posterior.
2. Crear el entorno virtual dentro de `backend`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements\development.txt
```

3. Copiar `.env.example` como `.env` y configurar la conexión local.
4. Registrar la línea base y crear las tablas internas de Django:

```powershell
python manage.py migrate
```

Las migraciones iniciales de `accounts`, `tenancy`, `rbac` y `audit` mantienen únicamente el
estado de los modelos existentes (`managed = False`); no recrean las 28 tablas de negocio.

5. Verificar el proyecto:

```powershell
python manage.py check
python manage.py spectacular --file openapi.yaml --validate
pytest
```

### Pruebas de integración con PostgreSQL

`pytest` corre en SQLite, donde no existen las tablas del esquema (`managed = False`). Lo que
depende de PostgreSQL —favoritos, reservas, cupos y pagos, con sus triggers, CHECK y bloqueos de
fila— se prueba aparte:

```powershell
pytest --ds=config.settings.test_pg tests/integracion
```

Usa el servidor PostgreSQL de `.env`, pero nunca su base: crea desde cero `situr_smart_pruebas`
con los scripts de `database/migrations`, `migrate`, un SuperAdmin y `seed_bolivia`. El usuario
de `.env` necesita permiso para crear bases.

## Base existente

Las tablas de negocio ya fueron creadas mediante los scripts de `database/migrations`. Los modelos
iniciales usan `managed = False` para impedir que Django intente recrearlas. La migración de línea
base ya fue generada y validada contra PostgreSQL 17. Los cambios futuros deberán incorporarse
mediante migraciones nuevas y revisadas; no se debe editar una migración ya aplicada en entornos
compartidos.

## Primer SuperAdmin

Con la base y los catálogos iniciales disponibles:

```powershell
python manage.py createsituradmin
```

La contraseña se procesa con los hashers de Django y nunca se guarda en texto plano.

## Datos de demostración

Con un SuperAdmin creado, carga empresas turísticas de Bolivia con hoteles, habitaciones,
restaurantes, tours, experiencias, atracciones, paquetes, empleados y turistas:

```powershell
python manage.py seed_bolivia                       # se puede repetir: lo que existe se omite
python manage.py seed_bolivia --reset               # borra lo que creó el seed y lo recarga
python manage.py seed_bolivia --limpiar-demo-viejo  # desactiva las empresas del seed anterior
python manage.py seed_bolivia --credenciales        # regenera CREDENCIALES_DEMO.md
python manage.py seed_bolivia --sql --limpiar-demo-viejo  # regenera database/seed_bolivia.sql
```

`database/seed_bolivia.sql` hace lo mismo que el comando y sirve para una base a la que no se
llega con `manage.py`: se abre en el Query Tool de pgAdmin y se ejecuta.

Los datos viven en `apps/catalog/seed/bolivia.py`. Todas las cuentas usan la contraseña
`Admin123*` y están listadas en `CREDENCIALES_DEMO.md`, en la raíz del repositorio. No se cargan
imágenes: se suben desde el panel.

## Administración interna de Django

Después de ejecutar las migraciones y crear el SuperAdmin, iniciar el servidor:

```powershell
python manage.py runserver
```

El panel interno estará disponible en `http://127.0.0.1:8000/admin/`. Se ingresa con el correo y
la contraseña registrados mediante `createsituradmin`. Este panel es una herramienta interna del
backend y no sustituye las pantallas administrativas que tendrá la aplicación web Angular.

## Despliegue en Railway

Configurar el servicio con el directorio raíz `/backend`. Railpack detecta `requirements.txt`,
instala las dependencias de producción y utiliza Python 3.12 según `.python-version`.

```text
Pre-Deploy: python manage.py migrate --noinput
Start:      gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
Health:     /api/v1/health/
```

### Cron de tareas programadas

Un segundo servicio de Railway, desde el mismo repositorio y con las mismas variables, corre cada
10 minutos `tareas_programadas`: vence las reservas sin pagar (con su aviso y push), completa las que
ya pasaron y, cuando toca segun la frecuencia elegida por el SuperAdmin, genera la copia de
seguridad, la guarda privada en Cloudinary y avisa por correo. El webhook de Stripe vence y
confirma reservas al instante; para eso el cron es el respaldo.

```text
Root:       /backend
Start:      python manage.py tareas_programadas
Cron:       */10 * * * *
```

El servicio no lleva Pre-Deploy ni Health: arranca, procesa y termina.

## Endpoints iniciales

```text
GET  /api/v1/health/
POST /api/v1/auth/login/
POST /api/v1/auth/refresh/
POST /api/v1/auth/logout/
GET  /api/v1/auth/me/
GET  /api/v1/permissions/
GET  /api/v1/roles/
POST /api/v1/roles/
GET  /api/v1/roles/{id}/
PATCH /api/v1/roles/{id}/
DELETE /api/v1/roles/{id}/
GET  /api/v1/usuarios/
POST /api/v1/usuarios/
GET  /api/v1/usuarios/{id}/
PATCH /api/v1/usuarios/{id}/
DELETE /api/v1/usuarios/{id}/
GET  /api/v1/catalogos/paises/
GET  /api/v1/catalogos/ciudades/
GET  /api/v1/catalogos/tipos-producto/
GET  /api/v1/catalogos/monedas/
GET  /api/v1/empresas/
POST /api/v1/empresas/
GET  /api/v1/empresas/{id}/
PATCH /api/v1/empresas/{id}/
PUT  /api/v1/empresas/{id}/propietario/
GET  /api/v1/productos/
POST /api/v1/productos/
GET  /api/v1/productos/{id}/
PATCH /api/v1/productos/{id}/
DELETE /api/v1/productos/{id}/
GET  /api/v1/marketplace/productos/
GET  /api/v1/marketplace/productos/{id}/
GET  /api/schema/
GET  /api/docs/
```

Los endpoints de tenant requieren el encabezado `X-Tenant-ID`. Este valor nunca concede acceso por
sí mismo: el backend valida la membresía activa y los permisos del usuario.

El Marketplace es público y solo devuelve productos con estado `PUBLICADO` pertenecientes a
empresas activas. Admite los filtros `pais`, `ciudad`, `localidad`, `tipo`, `fecha`, `buscar`,
`precio_min` y `precio_max`. El filtro por fecha consulta los bloques abiertos registrados en
`disponibilidad`.

## Comunicaciones internas y operativas (primera entrega)

El propietario o personal con `COMUNICACIONES_GESTIONAR` administra borradores y publicaciones
de su empresa usando `X-Tenant-ID`. Sin ese encabezado, solo el SuperAdmin administra avisos de
plataforma. Las lecturas y modificaciones de comunicaciones de otra empresa se rechazan.

Las audiencias internas incluyen personal con membresía activa. Las operativas pueden incluir
clientes con reservas pendientes, parciales, confirmadas o completadas de la empresa. Las reservas
canceladas y vencidas no crean una vinculación para enviar estos avisos. Un SuperAdmin puede
seleccionar toda la plataforma, empresas, personal, propietarios, clientes, roles o usuarios.
Las cuentas inactivas se excluyen y los destinatarios se deduplican por usuario.

```text
GET/POST  /api/v1/comunicaciones/
GET/PATCH /api/v1/comunicaciones/{id}/
GET       /api/v1/comunicaciones/opciones/?buscar=nombre
POST      /api/v1/comunicaciones/audiencia/
POST      /api/v1/comunicaciones/{id}/publicar/
GET       /api/v1/notificaciones/push-config/
```

Crear o editar requiere `titulo`, `mensaje`, `tipo` (`INTERNA` u `OPERATIVA`) y `audiencia`:
`grupo` (`TODOS`, `PERSONAL`, `CLIENTES`, `PROPIETARIOS`, `EMPLEADOS`, `USUARIOS`),
`empresa_ids`, `rol_ids`, `usuario_ids`, y opcionalmente `reserva_id` o `salida_id`.
Las selecciones adicionales se intersectan con el grupo y el alcance autorizado; nunca amplían
los permisos. Una reserva o salida restringe la audiencia a sus clientes. `reserva_id` en el
nivel principal permite enlazar esa reserva desde el aviso.

Después de guardar el borrador se envía el mismo contenido a `audiencia/`. La respuesta devuelve
destinatarios, cantidad y `huella`. Publicar requiere `{ "huella": "..." }`; si cambiaron contenido
o destinatarios responde 409. Repetir la publicación del mismo borrador publicado no duplica avisos.
Una publicación no puede editarse. Cada aviso conserva remitente y motivo de recepción.

La publicación crea notificaciones y entregas pendientes en una transacción. No espera a Firebase.
Las nuevas tablas `comunicacion`, `comunicacion_destinatario` y `comunicacion_push_intento` se crean
con `migrate`; la migración también registra el permiso y habilita dispositivos `WEB`.

### Worker persistente de push

Ejecutar un servicio separado con la misma base y configuración de Firebase que el backend:

```powershell
python manage.py process_communication_push --limit 100 --poll-seconds 5
# Para una tarea puntual o cron:
python manage.py process_communication_push --once --limit 100
```

La cola vive en PostgreSQL y sobrevive a reinicios; no requiere un broker adicional. Cada
dispositivo tiene hasta cinco intentos con espera creciente. Los tokens inválidos se retiran y
los dispositivos transferidos a otra cuenta no reciben el aviso de la cuenta anterior. Se admite
más de un worker con reclamaciones atómicas y recuperación de bloqueos vencidos.

`push_aceptados` cuenta destinatarios con al menos una aceptación por Firebase al finalizar sus
intentos. No acredita recepción ni lectura. `leidas` procede de la bandeja. Los dispositivos que
ya aceptaron el aviso no se reenvían en reintentos normales; una caída entre la aceptación externa
y su registro puede duplicar un push, por lo que no se promete entrega exactamente una vez.
Sin dispositivos se realizan cinco comprobaciones antes de marcar `SIN_DISPOSITIVO`.

### Push de navegador y móvil

La bandeja web permite activar/desactivar push mediante permiso explícito. Configurar las seis
variables públicas `FIREBASE_WEB_*` de `.env.example`, incluida la clave VAPID pública, y las
credenciales privadas de Firebase existentes en el backend. Servir Angular por HTTPS (localhost
también permite pruebas) y conservar `firebase-messaging-sw.js` en los assets publicados.
El endpoint de configuración solo expone los valores públicos; nunca la cuenta de servicio.
Sin configuración o permiso, la bandeja sigue funcionando.

En Flutter, clientes y personal reciben los avisos en Notificaciones; el personal conserva la
administración en el panel web. El proyecto Firebase de Android/iOS y los permisos del dispositivo
deben estar configurados para recibir push. El chat privado y la asistencia con IA quedan fuera de estas entregas.

## Campañas promocionales y programación (segunda entrega)

El editor permite elegir `PROMOCIONAL`, `programado_en`, `vence_en` y una oferta relacionada
(`promocion_id`). Las fechas viajan con zona horaria; el formulario usa la hora del dispositivo.
El vencimiento es obligatorio para publicidad y posterior al envío. Una oferta vinculada debe
pertenecer al alcance del remitente y estar habilitada; envío y vencimiento deben quedar dentro
de su vigencia. Las fechas también pueden utilizarse en avisos internos y operativos.

Después de revisar la audiencia y confirmar su huella, una publicación futura queda `PROGRAMADA`:
todavía no genera avisos de bandeja ni push. El worker `process_communication_push` procesa tanto
las campañas programadas como los push pendientes. Debe mantenerse ejecutándose para despachar
a la hora prevista; con `--once` procesa solo las tareas vencidas de ese momento.

La audiencia programada conserva los destinatarios revisados. Al despachar se comprueban de nuevo
la cuenta remitente, permisos, empresa, vinculación, consentimiento, límites y vigencia.
No se incorporan personas nuevas. Quienes ya no califican quedan omitidos. Si se perdió la
autorización o la oferta dejó de estar disponible, queda `REVISION`; se puede cancelar y preparar
un nuevo borrador. Si venció antes del despacho queda `VENCIDA` sin enviar.

```text
POST  /api/v1/comunicaciones/{id}/cancelar/
GET   /api/v1/me/comunicaciones/preferencias/
PATCH /api/v1/me/comunicaciones/preferencias/
```

Solo pueden cancelarse borradores, campañas programadas y pendientes de revisión. La cancelación
es idempotente y compite con el despacho bajo bloqueo de fila. El contenido confirmado no se edita
y cancelar no retira avisos previamente enviados.

Cada usuario administra únicamente sus preferencias: `{ "empresa_id": 7, "promociones": true }`.
`empresa_id: null` representa a SITUR-SMART como remitente independiente. Una preferencia ausente
significa publicidad desactivada. La lista incluye empresas vinculadas y preferencias anteriores
para permitir darse de baja. Desactivar publicidad no interfiere con reservas ni mensajes internos.
La web incorpora estos controles en Notificaciones; Flutter en el botón de preferencias de su bandeja.

Por defecto se admite una promoción por remitente y tres en total por usuario en una ventana móvil
de 24 horas. `COMMUNICATION_PROMOTIONS_PER_SENDER` y `COMMUNICATION_PROMOTIONS_PER_DAY` ajustan
los límites. El cómputo incluye campañas manuales y avisos automáticos de ofertas por intereses;
los mensajes operativos e internos no cuentan. La creación de avisos publicitarios se serializa
por usuario para evitar sobrepasar cuotas con publicaciones concurrentes. Una baja o vencimiento
se vuelve a comprobar antes del push de campaña.

Los avisos conservan su vencimiento para mostrarse como históricos; web y móvil deshabilitan el
acceso directo a una oferta vencida. Los avisos ya entregados no pueden retirarse. `omitidos`
incluye exclusiones por elegibilidad, baja o vencimiento. La migración `notifications.0007` añade
los campos de campaña y `comunicacion_preferencia`; no concede consentimiento a cuentas existentes.

## Correo y centro de comunicaciones

El editor dispone de plantillas de viaje, cambios, equipo y ofertas; permite personalizar
`{{nombre}}` y `{{empresa}}`, revisar el aspecto del mensaje y filtrar destinatarios por grupo,
empresa y rol. Las personas y roles disponibles se ajustan al alcance seleccionado. El listado
muestra borradores, programados y publicados, con búsqueda y conteos por estado del ámbito activo.
El SuperAdmin conserva el ámbito de plataforma o empresa; las empresas mantienen sus permisos
y el personal/guías reciben avisos en su bandeja. El acceso para publicar sigue requiriendo
`COMUNICACIONES_GESTIONAR` o ser propietario/SuperAdmin.

Cada publicación genera **notificación y correo juntos** para la misma audiencia y con el mismo
contenido: bandeja web/móvil, push y correo registrado, incluido Gmail. No hay un selector para
separarlos; `enviar_correo` es un campo de salida para consultar el historial. El backend aplica
este comportamiento también si un cliente antiguo intenta enviar `enviar_correo: false`.
Guardar y previsualizar nunca envían mensajes. La migración `notifications.0010` activa este
flujo en borradores y programaciones existentes; las publicaciones anteriores no se reenvían.

```text
GET /api/v1/comunicaciones/{id}/correo/       # Vista HTML y texto; mismo control de acceso
GET /api/v1/comunicaciones/?estado=BORRADOR&buscar=salida
GET /api/v1/comunicaciones/opciones/?empresa_ids=1,2&grupo=PERSONAL&rol_ids=4&tipo=OPERATIVA
```

Configurar en `backend/.env` las variables existentes `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`
(remitente verificado en Brevo) y `BREVO_SENDER_NAME`. No se necesita una clave de Gmail:
Brevo entrega al correo registrado de cada destinatario, incluido Gmail. Para pruebas locales:

```dotenv
WEB_APP_URL=http://localhost:4200
API_PUBLIC_URL=http://127.0.0.1:8000
```

En producción ambas direcciones deben ser públicas y usar HTTPS. Reiniciar el backend y el
worker después de cambiar la configuración. Para que una persona abra el enlace desde otro
dispositivo, las direcciones deben ser alcanzables desde ese dispositivo.

Aplicar `python manage.py migrate` y mantener el mismo worker:

```powershell
.\.venv\Scripts\python.exe manage.py process_communication_push --limit 100 --poll-seconds 5
# Un lote y terminar (se ejecuta en otra terminal o después de detener el anterior con Ctrl+C):
.\.venv\Scripts\python.exe manage.py process_communication_push --once --limit 100
```

Este proceso despacha programados, push y correo. La migración `notifications.0009` crea
`comunicacion_correo`. Hay un trabajo por destinatario, sin exponer direcciones de otras personas.
Solo se encola al publicar o al despachar una programación. Incluye versión HTML y texto,
enlaces a bandeja/reserva/oferta y contenido escapado; no interpreta HTML escrito en el editor.

Se registran `PENDIENTE`, `ACEPTADO`, `FALLIDO`, `OMITIDO` o `REVISION`, hasta cinco intentos
con espera creciente. Se comprueban de nuevo consentimiento, vigencia, cuenta y dirección antes
de enviar. El identificador de idempotencia se mantiene al reintentar; los resultados ambiguos
fuera de la ventana segura del proveedor quedan en revisión para evitar reenvíos ciegos.
`correos_aceptados` indica aceptación de Brevo: no acredita llegada a Gmail, apertura ni lectura.
La notificación y el trabajo de correo se crean en la misma transacción al publicar o despachar
una programación. Sus entregas se procesan por separado para poder reintentar cada proveedor;
no se promete recepción simultánea. Los errores de correo no eliminan el aviso de bandeja ni
detienen el push. El consentimiento promocional se aplica a ambos, por destinatario.

Las promociones usan el mismo consentimiento y presupuesto de frecuencia que web/móvil.
Su pie contiene un enlace firmado, limitado al usuario y remitente, válido por 90 días. Abrir
el enlace muestra una confirmación; solo su POST desactiva promociones. Los escáneres de correo
no provocan bajas con una visita GET. Los avisos operativos e internos continúan disponibles.

El diseño toma como referencia las [plantillas de Bókun](https://docs.bokun.io/en/articles/317-email-templates)
y la [mensajería de Cloudbeds](https://myfrontdesk.cloudbeds.com/hc/en-us/articles/8699946508187-Cloudbeds-Guest-Experience-Automated-Messages-Everything-You-Need-to-Know):
plantillas por situación del viaje, destinatarios segmentados y visibilidad del estado. Esta
entrega conserva la programación manual; no añade automatizaciones por eventos de reservas.
