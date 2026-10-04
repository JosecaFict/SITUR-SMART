from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied

from apps.backups.services import (
    BackupUnavailable,
    _safe_failure_message,
    generate_backup,
)


class BackupTests(SimpleTestCase):
    def test_classifies_version_mismatch_without_exposing_connection_data(self):
        code, message = _safe_failure_message(
            b'pg_dump: error: server version mismatch; host "secret.internal" user "postgres"'
        )

        self.assertEqual(code, "VERSION_INCOMPATIBLE")
        self.assertNotIn("secret.internal", message)
        self.assertNotIn('user "postgres"', message.lower())

    @patch("apps.backups.services.is_superadmin", return_value=False)
    def test_only_superadmin_can_generate_a_backup(self, _is_superadmin):
        with self.assertRaises(PermissionDenied):
            generate_backup(actor=Mock())

    @patch("apps.backups.services.is_superadmin", return_value=True)
    @patch("apps.backups.services.shutil.which", return_value=None)
    def test_reports_when_pg_dump_is_not_installed(self, _which, _is_superadmin):
        with self.assertRaises(BackupUnavailable):
            generate_backup(actor=Mock())

    @patch("apps.backups.services.is_superadmin", return_value=True)
    @patch("apps.backups.services.record_audit")
    @patch("apps.backups.services.subprocess.run")
    @patch("apps.backups.services.shutil.which", return_value="/usr/bin/pg_dump")
    def test_generates_a_custom_dump_and_audits_it(
        self, _which, run, record_audit, _is_superadmin
    ):
        def write_dump(_command, *, stdout, **_kwargs):
            stdout.write(b"PGDMP-test-content")
            return Mock(returncode=0, stderr=b"")

        run.side_effect = write_dump
        artifact = generate_backup(actor=Mock(is_authenticated=True))

        self.assertTrue(artifact.filename.endswith(".dump"))
        self.assertEqual(len(artifact.sha256), 64)
        self.assertEqual(artifact.file.read(), b"PGDMP-test-content")
        record_audit.assert_called_once()
