import base64
import importlib.util
import io
import os
import pathlib
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('wb_backup', pathlib.Path(__file__).parents[1] / 'src/wb_backup.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        content = io.BytesIO()
        with tarfile.open(fileobj=content, mode='w:gz') as archive:
            data = os.urandom(4096)
            member = tarfile.TarInfo('etc/test.conf')
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        self.archive = content.getvalue()

    def script(self, body):
        script = self.root / 'native'
        script.write_text('#!' + sys.executable + '\n' + body)
        script.chmod(0o700)
        return script

    def test_legacy_archive_and_private_permissions(self):
        script = self.script('import base64,sys\nsys.stdout.buffer.write(base64.b64decode(' + repr(base64.b64encode(self.archive)) + '))\n')
        target = self.root / 'backup.partial'
        with mock.patch.dict(backup.NATIVE_SCRIPTS, {'config': script}):
            backup.create_archive('config', target)
        self.assertEqual(target.read_bytes(), self.archive)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_modern_full_environment_cgi_and_large_diagnostics(self):
        script = self.script('import base64,os,sys\nassert os.environ["WB_BACKUP_TYPE"] == "everything"\nsys.stderr.write("diagnostic\\n" * 20000)\nsys.stderr.flush()\nsys.stdout.buffer.write(b"Status: 200\\r\\nContent-Type: application/octet-stream\\r\\n\\r\\n" + base64.b64decode(' + repr(base64.b64encode(self.archive)) + '))\n')
        target = self.root / 'backup.partial'
        with mock.patch.dict(backup.NATIVE_SCRIPTS, {'full': self.root / 'missing'}), mock.patch.object(backup, 'NATIVE_BACKUP', script):
            backup.create_archive('full', target)
        self.assertEqual(target.read_bytes(), self.archive)

    def test_archive_permissions_override_inherited_acl(self):
        script = self.script('import base64,sys\nsys.stdout.buffer.write(base64.b64decode(' + repr(base64.b64encode(self.archive)) + '))\n')
        target = self.root / 'backup.partial'
        original_open = os.open
        def inherited_acl(*args, **kwargs):
            fd = original_open(*args, **kwargs)
            os.fchmod(fd, 0o777)
            return fd
        with mock.patch.dict(backup.NATIVE_SCRIPTS, {'config': script}), mock.patch.object(backup.os, 'open', side_effect=inherited_acl):
            backup.create_archive('config', target)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_modern_configs_only_include_installed_optional_apps(self):
        script = self.script('pass\n')
        installed = self.root / 'installed-app'
        installed.mkdir()
        absent = self.root / 'absent-app'
        with mock.patch.dict(backup.NATIVE_SCRIPTS, {'config': self.root / 'missing'}), mock.patch.object(backup, 'NATIVE_BACKUP', script), mock.patch.object(backup, 'OPTIONAL_CONFIG_PATHS', (installed, absent)):
            command = backup.archive_command('config', {})
        self.assertIn('/etc', command)
        self.assertIn('/mnt/data/etc', command)
        self.assertIn(str(installed), command)
        self.assertNotIn(str(absent), command)

    def test_gzip_crc_failure_is_rejected(self):
        target = self.root / 'corrupt.tar.gz'
        data = bytearray(self.archive)
        data[-8] ^= 1
        target.write_bytes(data)
        with self.assertRaises((OSError, EOFError)):
            backup.validate_archive(target)

    def test_exporter_failure_does_not_become_success(self):
        script = self.script('import base64,sys\nsys.stdout.buffer.write(base64.b64decode(' + repr(base64.b64encode(self.archive)) + '))\nsys.exit(2)\n')
        with mock.patch.dict(backup.NATIVE_SCRIPTS, {'config': script}):
            with self.assertRaisesRegex(RuntimeError, 'failed \\(2\\)'):
                backup.create_archive('config', self.root / 'backup.partial')

    def test_invalid_cgi_body_is_rejected(self):
        script = self.script('import sys\nsys.stdout.buffer.write(b"Status: 500\\n\\nNot an archive")\n')
        with mock.patch.dict(backup.NATIVE_SCRIPTS, {'config': script}):
            with self.assertRaisesRegex(RuntimeError, 'not a gzip archive'):
                backup.create_archive('config', self.root / 'backup.partial')

    def test_live_journal_changes_are_accepted_with_warning(self):
        script = self.script('import base64,sys\nsys.stderr.write("/usr/bin/tar: Removing leading `/\' from member names\\n/usr/bin/tar: /mnt/data/var/log/journal/system.journal: file changed as we read it\\n")\nsys.stdout.buffer.write(base64.b64decode(' + repr(base64.b64encode(self.archive)) + '))\nsys.exit(1)\n')
        with mock.patch.dict(backup.NATIVE_SCRIPTS, {'full': script}):
            warning = backup.create_archive('full', self.root / 'backup.partial')
        self.assertIn('Live log files changed', warning)

    def test_config_changes_are_rejected(self):
        script = self.script('import base64,sys\nsys.stderr.write("tar: /etc/important.conf: file changed as we read it\\n")\nsys.stdout.buffer.write(base64.b64decode(' + repr(base64.b64encode(self.archive)) + '))\nsys.exit(1)\n')
        with mock.patch.dict(backup.NATIVE_SCRIPTS, {'config': script}):
            with self.assertRaisesRegex(RuntimeError, 'failed \\(1\\)'):
                backup.create_archive('config', self.root / 'backup.partial')

    def test_real_error_after_long_log_is_rejected(self):
        diagnostics = ("tar: /var/log/system.log: file changed as we read it\n" * 1000
                       + "tar: /etc/important.conf: Permission denied\n")
        with io.BytesIO(diagnostics.encode()) as stream:
            self.assertFalse(backup.only_live_logs_changed(1, stream))


if __name__ == '__main__':
    unittest.main()
