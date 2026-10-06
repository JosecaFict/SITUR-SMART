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

## Verificación

```powershell
flutter pub get
flutter analyze
flutter test
```
