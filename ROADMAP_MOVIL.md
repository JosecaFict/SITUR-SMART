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
| 3.4 | Push con Firebase (FCM) | **Pendiente** |
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
- **Notificaciones**: primero en la app (hecho); el push de Firebase se engancha en
  `backend/apps/notifications/services.py::notify()`, sin tocar reservas ni pagos.

## Pendiente de configurar

- **Railway**: ya están `STRIPE_SECRET_KEY` y `STRIPE_PUBLISHABLE_KEY`. Falta
  `STRIPE_WEBHOOK_SECRET`. Después del deploy: Stripe (modo prueba) → Developers → Webhooks →
  Add endpoint → `https://situr-smart-production.up.railway.app/api/v1/pagos/stripe/webhook/`,
  eventos `checkout.session.completed` y `checkout.session.expired`; el *Signing secret*
  (`whsec_…`) va a Railway.
- **Firebase (para 3.4)**: crear el proyecto, agregar la app Android `bo.situr.smart`, descargar
  `google-services.json` y generar una clave de cuenta de servicio para Railway.
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
