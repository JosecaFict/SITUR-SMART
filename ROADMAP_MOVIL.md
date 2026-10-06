# Hoja de ruta de la app móvil (turista)

Estado al 2026-10-06. La app Flutter (`mobile/`) es la app del **turista**; el panel de empresas
y del SuperAdmin vive en la web.

## Etapas

| Etapa | Contenido | Estado |
|---|---|---|
| 1 | Registro, recuperación con OTP, renovación de sesión, id `bo.situr.smart` | Hecha |
| 2 | Explorar, fichas de hospedaje y producto, Asistente IA (chat y voz), Mi Perfil | Hecha |
| 3.1 | Favoritos | Hecha |
| 3.2 | Reservas con cupo automático, pago con Stripe Checkout, voucher con QR, Mis viajes | Hecha |
| 3.3 | Notificaciones en la app y correo de reserva confirmada (Brevo) | Hecha |
| 3.4 | Push con Firebase (FCM): aviso en el celular y al tocarlo abre la reserva | Hecha |
| 3.5 | Itinerarios | **Pendiente** |

Pruebas manuales: se decidió probar **todo junto en el APK al final**, no etapa por etapa.

## Decisiones tomadas

- **Cupos automáticos.** Nadie carga disponibilidad: una habitación ofrece su
  `cantidad_habitaciones` por noche; tour, experiencia, atracción, restaurante y paquete ofrecen
  su `capacidad_maxima` por día. La fila de `disponibilidad` se crea al reservar.
- **Stripe Checkout en modo prueba** (página de Stripe, no PaymentSheet nativo). Confirmación por
  webhook; si no llega, consultar la reserva concilia con Stripe.
- Solo se cancela **antes de pagar**. Cancelar una reserva pagada (reembolso, políticas de
  penalización) queda para más adelante.
- **QR sin prioridad**: el voucher existe; no se hará el escáner para empresas.
- **Notificaciones**: se guardan en la bandeja y salen por push desde
  `backend/apps/notifications/services.py::notify()`; reservas y pagos no saben de Firebase.
  El celular se registra al iniciar sesión (`me/dispositivos/`) y se quita al cerrarla.

## Configuración

Ya cargada:

- **Stripe**: `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` y `STRIPE_WEBHOOK_SECRET` en Railway.
  Endpoint en Stripe (modo prueba):
  `https://situr-smart-production.up.railway.app/api/v1/pagos/stripe/webhook/`, eventos
  `checkout.session.completed` y `checkout.session.expired`.
- **Firebase**: proyecto `situr-smart-ac780` (cuenta Gmail personal: el correo institucional no
  deja crear claves de cuenta de servicio). `mobile/android/app/google-services.json` va en el
  repo (no es secreto). La clave de la cuenta de servicio va **solo** en Railway como
  `FIREBASE_CREDENTIALS_BASE64`; `GET /api/v1/health/` muestra `"firebase": true` si se lee bien.

Pendiente:

- **Opcional**: `openapi.yaml` está desactualizado desde antes de estas etapas; regenerarlo en un
  commit propio.

## Verificación

```powershell
# Backend (en backend/)
pytest                                                   # suite normal en SQLite
pytest --ds=config.settings.test_pg tests/integracion    # PostgreSQL real: favoritos, reservas, pagos, avisos
python manage.py migrate                                 # crea favorito, notificacion y columnas de reserva

# Móvil (en mobile/)
flutter pub get
flutter analyze
flutter test
```

La suite de integración crea su propia base `situr_smart_pruebas` en el PostgreSQL de `.env`
(necesita permiso para crear bases) y nunca toca la base de desarrollo.

## Checklist del APK (prueba final)

Registro e inicio de sesión · Explorar con filtros · ficha de hospedaje y "Ver en el mapa" ·
favoritos · reservar una habitación y un tour · pagar con `4242 4242 4242 4242` · ver la reserva
confirmada con su QR en Viajes · notificación y correo de confirmación · reserva sin pagar que
vence o se cancela · Asistente por texto y por voz · Mi Perfil.
