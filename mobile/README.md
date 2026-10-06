# Mobile SITUR-SMART

Aplicación Flutter que consume la misma API Django utilizada por la aplicación web.
Identificador de la app: `bo.situr.smart` (Android e iOS).

## Configuración de la API

La URL no está escrita directamente en el código. Se configura al ejecutar o compilar mediante
`API_URL`.

Backend desplegado en Railway (el mismo que usa la web):

```powershell
flutter run --dart-define=API_URL=https://situr-smart-production.up.railway.app/api/v1/
```

Emulador Android con backend local:

```powershell
flutter run --dart-define=API_URL=http://10.0.2.2:8000/api/v1/
```

Teléfono físico en la misma red que la computadora:

```powershell
flutter run --dart-define=API_URL=http://IP-DE-LA-COMPUTADORA:8000/api/v1/
```

Para generar un APK conectado a Railway se incluye el mismo `--dart-define`:

```powershell
flutter build apk --dart-define=API_URL=https://situr-smart-production.up.railway.app/api/v1/
```

Sin `--dart-define`, la app usa `http://10.0.2.2:8000/api/v1/` (emulador contra backend local).

## Sesión

- Al abrir la app, si hay una sesión guardada se renueva sola y se entra directo.
- Cuando el access token vence, la app lo renueva con el refresh token y repite la petición. Si
  la sesión ya no se puede renovar, vuelve al login.
- Los turistas (rol CLIENTE) entran a **Explorar**; el personal de empresas y el SuperAdmin, al
  panel.
- Las cuentas de prueba están en `CREDENCIALES_DEMO.md`, en la raíz del repositorio.

## App del turista

Barra inferior con tres pestañas, que conservan su estado al cambiar entre ellas:

- **Explorar**: marketplace público (`marketplace/productos/` y `marketplace/hospedajes/`) con
  búsqueda, categorías, filtros de ciudad, precio y orden, y carga de más resultados al llegar al
  final. Un hospedaje abre su ficha con servicios, ubicación en OpenStreetMap y tipos de
  habitación; los demás productos abren su detalle.
- **Asistente**: chat con el asistente IA (`asistente/chat/`). Las recomendaciones de hospedaje
  abren su ficha. El micrófono graba una nota de hasta 30 s, el backend la transcribe
  (`asistente/voz/`) y el texto queda en la caja para revisarlo antes de enviarlo. Si el backend
  no tiene proveedor de IA configurado, la pestaña lo indica.
- **Mi Perfil**: datos personales y documento (`GET/PATCH auth/me/`), cambio de contraseña y
  cierre de sesión.
- **Favoritos**: corazón en tarjetas y fichas (`me/favoritos/`).
- **Viajes**: reservas del turista (`me/reservas/`). Se reserva desde la habitación de un
  hospedaje o desde la ficha de un tour, experiencia, atracción, restaurante o paquete; el pago se
  abre en Stripe Checkout y la reserva se confirma sola al volver a la app. Las pagadas muestran
  su voucher con QR.
- **Notificaciones**: campana con el contador de no leídas en las pestañas
  (`me/notificaciones/`). Se pone al día cada minuto y al volver a la app; al confirmarse una
  reserva también llega un correo (Brevo).

Pago de prueba: tarjeta `4242 4242 4242 4242`, cualquier fecha futura y cualquier CVC.

Permisos: micrófono (`RECORD_AUDIO` en Android, `NSMicrophoneUsageDescription` en iOS), pedido
la primera vez que se usa la voz.

## Verificación

```powershell
flutter pub get
flutter analyze
flutter test
```
