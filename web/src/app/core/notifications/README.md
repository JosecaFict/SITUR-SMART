# Push de navegador

`WebPushService` es un servicio raíz; no necesita cambios de providers, rutas ni menú.
Usa `environment.apiUrl` y el interceptor de autenticación existente. El SDK Firebase
se importa de forma diferida al activar push. No hay credenciales privadas en el cliente.

## Integración con la bandeja

```ts
readonly push = inject(WebPushService);

// En el shell al iniciar con la sesión restaurada; no solicita permisos:
void this.push.restore();

// Al iniciar la bandeja, antes del clic de activación:
await this.push.loadConfig();
await this.push.restore();

// En el manejador del botón del usuario:
await this.push.activate();

// Para desactivar o antes de auth.logout(), con sesión vigente:
const removed = await this.push.deactivate();
```

Los métodos devuelven promesas; activar/desactivar devuelve `boolean` y expone el
mensaje en `error()`. `false` permite mostrar el fallo y reintentar. `status()` usa
`idle`, `loading`, `unsupported`, `unavailable`, `denied`, `inactive`, `activating`,
`active`, `deactivating`, `error`. También están disponibles `config()`, `permission()`,
`supported()`, `busy()` y `enabled()`. El permiso del navegador no se revoca al
desactivar: se elimina el token de la API y la suscripción Firebase.

Precargar `loadConfig()` evita perder el gesto del usuario al pedir permiso en Safari.
No pide permiso ni inicializa Firebase. `restore()` revalida/renueva el token y
conecta la recepción en primer plano solo cuando hay un token guardado, registrado
para la cuenta actual y con permiso ya concedido. Solo entonces consulta configuración
si falta. Vuelve a comprobar cuenta, consentimiento y permiso tras la consulta; si se
desactiva durante la restauración no vuelve a activar la suscripción. Nunca solicita
permiso, incluso si cambia mientras espera al servidor, SDK o worker. Debe llamarse
desde el shell/init autenticado para restaurar también fuera de la bandeja. No se
realiza activación automática durante la construcción del servicio.

Suscribirse a `foregroundMessages$` para actualizar la bandeja/contador y destruir la
suscripción con `takeUntilDestroyed`. En primer plano no se crea un aviso del sistema.
La bandeja conserva sus consultas normales cuando push no está disponible.

## Contrato del backend

- `GET /notificaciones/push-config/`: `{habilitado, firebase: {apiKey, authDomain,
  projectId, messagingSenderId, appId}, vapid_key}`. Todos los campos Firebase y la
  clave pública VAPID deben estar completos. Un 404, configuración incompleta o
  `habilitado: false` dejan push no disponible y permiten reintentar.
- `POST /me/dispositivos/`: `{token, plataforma: 'WEB'}` con token de registro FCM.
- `POST /me/dispositivos/quitar/`: `{token}` con la sesión todavía vigente.

El servicio conserva el token y los campos públicos Firebase en localStorage para
permitir la desactivación tras una recarga incluso si falta el endpoint de configuración.
El cliente cancela primero la suscripción Web Push del scope dedicado; si hay una
instancia Firebase activa también elimina el token mediante el SDK. Tras una recarga
usa la cancelación nativa y el retiro del token en la API, evitando que `deleteToken`
registre un worker por defecto distinto al configurado. El SDK reemplazará su token
en caché al activar de nuevo sobre una suscripción nueva.
Los retiros de API y Firebase se intentan ambos aunque uno falle; se conserva la
información para reintentar si la limpieza queda incompleta. Las operaciones repetidas
se agrupan y activar/desactivar se serializan.

El servicio también observa la cuenta autenticada: si desaparece o cambia, revoca
localmente el token FCM, cubriendo expiración de sesión y eliminación de cuenta. Ya
sin el bearer anterior no intenta retirar ese token en nombre de otra cuenta; el
backend puede depurar el token revocado al recibir el rechazo de FCM. Antes del
logout explícito se debe seguir esperando `deactivate()` para retirarlo de la API.
Si falla la revocación tras perder sesión, se reintenta también al recuperar conexión.

## Worker y despliegue

`web/public/firebase-messaging-sw.js` se copia por la configuración Angular existente.
Se registra relativo a `document.baseURI` con un scope dedicado
`firebase-cloud-messaging-push-scope/`, sin reemplazar un worker de la aplicación.
Recibe únicamente configuración pública Firebase en query params, disponible también
cuando el navegador reinicia el worker sin ventanas abiertas. El worker importa los
scripts compat de Firebase desde `https://www.gstatic.com/firebasejs/13.4.0/`;
mantener esta versión alineada con la dependencia Firebase del proyecto.

Se requiere HTTPS (o localhost), soporte de Notification/Push/ServiceWorker/IndexedDB,
y una configuración Firebase/VAPID válida. Si hay una CSP, debe permitir el worker,
los scripts de gstatic y las conexiones de Firebase Messaging/Installations. El servidor
debe servir el worker como JavaScript y no devolver el HTML de Angular en esa URL.

FCM muestra automáticamente payloads con `notification`; el worker muestra solo los
payloads exclusivamente `data`, evitando duplicados. Al hacer clic acepta únicamente
`data.ruta` en forma `/ruta` del mismo origen. En otro caso abre `notificaciones`
relativo al directorio de la aplicación. Ignora links externos de FCM y reutiliza una
ventana de la aplicación cuando es posible.

## Comprobaciones locales

```sh
npm run build
npm test -- --watch=false --browsers=ChromeHeadless --include=src/app/core/notifications/*.spec.ts
node --test src/app/core/notifications/firebase-messaging-sw.test.cjs
```

Una prueba real de entrega requiere el endpoint configurado y un proyecto Firebase
con Web Push habilitado; las pruebas locales no contactan FCM.
