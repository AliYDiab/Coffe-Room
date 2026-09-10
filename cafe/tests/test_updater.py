import unittest
from pathlib import Path

import updater


class UpdaterContractTests(unittest.TestCase):
    def test_selects_windows_exe_from_combined_release(self):
        release = {
            "assets": [
                {"name": "CafeRoom-Mobile-v1.6.0.apk", "browser_download_url": "apk"},
                {"name": "SHA256SUMS-v1.6.0.txt", "browser_download_url": "sha"},
                {"name": "CafeRoom-PC-v1.6.0.exe", "browser_download_url": "exe"},
            ]
        }

        selected = updater.select_windows_update_asset(release)

        self.assertEqual(selected["name"], "CafeRoom-PC-v1.6.0.exe")

    def test_missing_windows_asset_is_reported(self):
        release = {"assets": [{"name": "CafeRoom-Mobile-v1.6.0.apk"}]}
        self.assertIsNone(updater.select_windows_update_asset(release))

    def test_exe_replacement_commands_have_bounded_retries_and_restart(self):
        commands = updater.build_exe_update_commands(
            Path(r"C:\Temp\CafeRoom-PC-v1.6.0.exe"),
            Path(r"C:\CafeRoom\CafeRoom.exe"),
            max_attempts=30,
        )
        script = "\n".join(commands)

        self.assertIn("set /a attempts+=1", script)
        self.assertIn("if !attempts! GEQ 30 goto update_failed", script)
        self.assertIn('start "" "C:\\CafeRoom\\CafeRoom.exe"', script)
        self.assertIn("CafeRoom-update-error.log", script)


if __name__ == "__main__":
    unittest.main()
