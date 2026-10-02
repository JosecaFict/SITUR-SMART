# Mobile SITUR-SMART

Aplicación Flutter que consume la misma API Django utilizada por la aplicación web.

## Configuración de la API

La URL no está escrita directamente en el código. Se configura al ejecutar o compilar mediante
`API_URL`.

Emulador Android con backend local:

```powershell
flutter run --dart-define=API_URL=http://10.0.2.2:8000/api/v1/
```

Teléfono físico en la misma red que la computadora:

```powershell
flutter run --dart-define=API_URL=http://IP-DE-LA-COMPUTADORA:8000/api/v1/
```

Backend desplegado en Railway:

```powershell
flutter run --dart-define=API_URL=https://DOMINIO-RAILWAY/api/v1/
```

Para generar un APK conectado a Railway se debe incluir el mismo `--dart-define` en
`flutter build apk`.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Learn Flutter](https://docs.flutter.dev/get-started/learn-flutter)
- [Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Flutter learning resources](https://docs.flutter.dev/reference/learning-resources)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.
