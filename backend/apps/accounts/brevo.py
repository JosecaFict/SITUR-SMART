import json
import logging
import urllib.error
import urllib.request
from django.conf import settings

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def build_otp_email_html(recipient_name: str, otp_code: str, expiration_minutes: int) -> str:
    """Construye una plantilla HTML moderna con la identidad visual de SITUR-SMART."""
    name_display = recipient_name if recipient_name and recipient_name.strip() else "Usuario"
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Código de recuperación - SITUR-SMART</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f1f5f9; padding: 32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 520px; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); overflow: hidden; border: 1px solid #e2e8f0;">
          <!-- Header Banner -->
          <tr>
            <td style="background: linear-gradient(135deg, #0d5c58 0%, #115e59 100%); padding: 32px 24px; text-align: center;">
              <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 800; letter-spacing: 0.5px;">SITUR-SMART</h1>
              <p style="margin: 6px 0 0 0; color: #99f6e4; font-size: 13px; font-weight: 500;">Plataforma de Gestión Turística</p>
            </td>
          </tr>

          <!-- Content -->
          <tr>
            <td style="padding: 32px 28px;">
              <h2 style="margin: 0 0 12px 0; color: #0f172a; font-size: 19px; font-weight: 700;">Recuperación de contraseña</h2>
              <p style="margin: 0 0 20px 0; color: #475569; font-size: 14px; line-height: 1.6;">
                Hola <strong>{name_display}</strong>, recibimos una solicitud para restablecer la contraseña de tu cuenta en SITUR-SMART.
              </p>
              
              <p style="margin: 0 0 16px 0; color: #475569; font-size: 14px;">
                Ingresa el siguiente código de verificación de 6 dígitos:
              </p>

              <!-- OTP Code Display -->
              <div style="background-color: #f0fdfa; border: 2px dashed #14b8a6; border-radius: 12px; padding: 20px; text-align: center; margin: 24px 0;">
                <span style="display: inline-block; font-size: 34px; font-weight: 800; letter-spacing: 8px; color: #0f766e; font-family: monospace;">{otp_code}</span>
              </div>

              <!-- Expiration Warning -->
              <p style="margin: 0 0 20px 0; color: #64748b; font-size: 13px; line-height: 1.5;">
                ⏱️ Este código es válido por <strong>{expiration_minutes} minutos</strong>. Por seguridad, no lo compartas con nadie.
              </p>

              <div style="border-top: 1px solid #e2e8f0; margin-top: 24px; padding-top: 20px;">
                <p style="margin: 0; color: #94a3b8; font-size: 12px; line-height: 1.5;">
                  Si no solicitaste este código, puedes ignorar este correo de forma segura. Tu contraseña actual no cambiará.
                </p>
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #f8fafc; padding: 18px 24px; text-align: center; border-top: 1px solid #e2e8f0;">
              <p style="margin: 0; color: #94a3b8; font-size: 11px;">
                © 2026 SITUR-SMART. Todos los derechos reservados.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def send_password_reset_otp_email(
    *,
    to_email: str,
    recipient_name: str,
    otp_code: str,
    expiration_minutes: int = 15,
) -> bool:
    """
    Envía un correo electrónico con el código OTP usando la API de Brevo.
    Si BREVO_API_KEY no está configurada, registra el código en la consola para desarrollo local.
    """
    api_key = getattr(settings, "BREVO_API_KEY", "").strip()
    sender_email = getattr(settings, "BREVO_SENDER_EMAIL", "jcvillarroeld126@ficct.uagrm.edu.bo").strip()
    sender_name = getattr(settings, "BREVO_SENDER_NAME", "SITUR-SMART").strip()

    if not api_key:
        logger.info(
            "[DEV / FALLBACK] BREVO_API_KEY no configurada. Código OTP para %s: %s (expira en %d min)",
            to_email,
            otp_code,
            expiration_minutes,
        )
        return True

    html_content = build_otp_email_html(recipient_name, otp_code, expiration_minutes)

    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email,
        },
        "to": [
            {
                "email": to_email,
                "name": recipient_name if recipient_name else to_email,
            }
        ],
        "subject": f"Código de recuperación: {otp_code} - SITUR-SMART",
        "htmlContent": html_content,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BREVO_API_URL,
        data=data,
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
            "User-Agent": "SITUR-SMART/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            if 200 <= status_code < 300:
                logger.info("Correo OTP de recuperación enviado exitosamente a %s vía Brevo.", to_email)
                return True
            logger.error("Brevo respondió con código no esperado: %d", status_code)
            return False
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        logger.error("Error HTTP al llamar a Brevo API (%d): %s", exc.code, error_body)
        return False
    except urllib.error.URLError as exc:
        logger.error("Error de conexión al llamar a Brevo API: %s", exc.reason)
        return False
    except Exception as exc:
        logger.exception("Error inesperado enviando correo OTP con Brevo: %s", exc)
        return False
