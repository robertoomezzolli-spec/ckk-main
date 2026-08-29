import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.sovereign.backup import backup_once  # noqa: E402


class SovereignBackupTests(unittest.TestCase):
    def test_online_backup_is_readable_and_retention_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "state.sqlite3"
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE identity (head TEXT NOT NULL)")
                connection.execute("INSERT INTO identity VALUES ('abc')")
            backup_dir = root / "backups"
            first = backup_once(database, backup_dir, retain=2)
            with sqlite3.connect(first) as connection:
                self.assertEqual(connection.execute("SELECT head FROM identity").fetchone()[0], "abc")
            # Pre-existing older recovery points are pruned after a valid backup.
            (backup_dir / "sovereign-00000000T000000Z.sqlite3").write_bytes(b"old")
            (backup_dir / "sovereign-00000001T000000Z.sqlite3").write_bytes(b"old")
            backup_once(database, backup_dir, retain=2)
            self.assertLessEqual(len(list(backup_dir.glob("sovereign-*.sqlite3"))), 2)

    def test_backup_refuses_zero_recovery_depth(self):
        with self.assertRaises(ValueError):
            backup_once(Path("missing"), Path("unused"), retain=1)


if __name__ == "__main__":
    unittest.main()
