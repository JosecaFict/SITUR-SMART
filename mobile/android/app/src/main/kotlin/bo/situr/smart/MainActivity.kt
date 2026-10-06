package bo.situr.smart

import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity

class MainActivity : FlutterActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        createNotificationChannel()
    }

    // Canal de los avisos push. El backend manda cada push a "situr_avisos"
    // (apps/notifications/push.py); con importancia alta Android lo muestra
    // como banner y no solo en la barra.
    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            getString(R.string.notification_channel_id),
            "Avisos de reservas",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = "Reserva confirmada, vencida o cancelada."
        }
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }
}
