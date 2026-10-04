from typing import ClassVar

from django.http import FileResponse
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .services import generate_backup


class BackupDownloadView(APIView):
    throttle_classes: ClassVar[list[type[ScopedRateThrottle]]] = [ScopedRateThrottle]
    throttle_scope = "backup"

    def post(self, request):
        artifact = generate_backup(actor=request.user, request=request)
        response = FileResponse(
            artifact.file,
            as_attachment=True,
            filename=artifact.filename,
            content_type="application/octet-stream",
        )
        response["Content-Length"] = str(artifact.size)
        response["X-Backup-SHA256"] = artifact.sha256
        response["Cache-Control"] = "no-store"
        return response
