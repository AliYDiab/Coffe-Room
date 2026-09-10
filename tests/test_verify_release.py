import tempfile
import unittest
from pathlib import Path

from scripts.verify_release import verify_artifacts, write_checksums


class ReleaseVerificationTests(unittest.TestCase):
    def test_verifies_both_platform_assets_and_writes_checksums(self):
        with tempfile.TemporaryDirectory() as temp:
            release_dir = Path(temp)
            (release_dir / "CafeRoom-Mobile-v1.6.0.apk").write_bytes(b"PK\x03\x04android")
            (release_dir / "CafeRoom-PC-v1.6.0.exe").write_bytes(b"MZwindows")

            hashes = verify_artifacts(release_dir, "1.6.0")
            checksum_path = write_checksums(release_dir, "1.6.0", hashes)

            self.assertEqual(set(hashes), {
                "CafeRoom-Mobile-v1.6.0.apk",
                "CafeRoom-PC-v1.6.0.exe",
            })
            text = checksum_path.read_text(encoding="utf-8")
            self.assertIn("CafeRoom-Mobile-v1.6.0.apk", text)
            self.assertIn("CafeRoom-PC-v1.6.0.exe", text)

    def test_rejects_release_missing_a_platform_asset(self):
        with tempfile.TemporaryDirectory() as temp:
            release_dir = Path(temp)
            (release_dir / "CafeRoom-PC-v1.6.0.exe").write_bytes(b"MZwindows")

            with self.assertRaisesRegex(RuntimeError, "Mobile"):
                verify_artifacts(release_dir, "1.6.0")


if __name__ == "__main__":
    unittest.main()
