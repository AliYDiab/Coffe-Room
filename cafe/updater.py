import os
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
import requests
from packaging import version

from version import __version__


REPO = os.getenv("CAFE_UPDATE_REPO", "AliYDiab/Coffe-Room")
GITHUB_API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"

PROTECTED_FILES = {
    "cafe.db",
    "cafe.db-shm",
    "cafe.db-wal",
    "device_token.txt",
    "firebase_key.json",
}


def check_for_updates(root=None, silent=True):
    """Check GitHub releases without blocking the POS startup."""
    worker = threading.Thread(
        target=_check_for_updates_worker,
        args=(root, silent),
        daemon=True,
    )
    worker.start()
    return worker


def _check_for_updates_worker(root, silent):
    try:
        release = _get_latest_release()
        latest = _release_version(release)
        current = version.parse(__version__)

        if latest <= current:
            return

        asset = select_windows_update_asset(release)
        if not asset:
            raise RuntimeError("The latest release has no .exe or .zip asset.")

        _run_on_ui(root, lambda: _ask_to_install_update(root, latest, asset, release))
    except Exception as exc:
        print("Updater error:", exc)
        if not silent:
            _run_on_ui(root, lambda: messagebox.showerror(
                "Update Error",
                f"Could not check for updates:\n{exc}",
            ))


def _get_latest_release():
    response = requests.get(GITHUB_API_URL, timeout=15)
    response.raise_for_status()
    return response.json()


def _release_version(release):
    tag = release.get("tag_name", "").strip().lstrip("vV")
    if not tag:
        raise RuntimeError("Latest release does not have a version tag.")
    return version.parse(tag)


def select_windows_update_asset(release):
    assets = release.get("assets") or []
    if not assets:
        return None

    current_name = Path(sys.executable).name.lower()
    candidates = [
        asset for asset in assets
        if asset.get("name", "").lower().endswith((".exe", ".zip"))
    ]
    if not candidates:
        return None

    for asset in candidates:
        name = asset.get("name", "").lower()
        if name.startswith("caferoom-pc-") and name.endswith(".exe"):
            return asset

    for asset in candidates:
        if asset.get("name", "").lower() == current_name:
            return asset

    for extension in (".exe", ".zip"):
        for asset in candidates:
            if asset.get("name", "").lower().endswith(extension):
                return asset

    return candidates[0]


class _UpdateProgressDialog:
    def __init__(self, root, latest, asset, release):
        self.root = root
        self.latest = latest
        self.asset = asset
        self.release = release
        self.started = False

        self.win = ctk.CTkToplevel(root)
        self.win.title("CafeRoom Update")
        self.win.geometry("520x460")
        self.win.minsize(480, 420)
        self.win.transient(root)
        self.win.lift()
        self.win.focus_force()
        self.win.grab_set()
        self.win.protocol("WM_DELETE_WINDOW", self.cancel)

        body = ctk.CTkFrame(self.win, fg_color="#241c11", corner_radius=16)
        body.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(
            body,
            text="Update Available",
            font=("Tahoma", 24, "bold"),
            text_color="#f5c400",
        ).pack(anchor="w", padx=18, pady=(18, 4))

        ctk.CTkLabel(
            body,
            text=f"Current: {__version__}   →   Latest: {latest}",
            font=("Tahoma", 15, "bold"),
            text_color="#e8dcc0",
        ).pack(anchor="w", padx=18, pady=(0, 12))

        size_text = _format_bytes(asset.get("size") or 0)
        ctk.CTkLabel(
            body,
            text=f"File: {asset.get('name', 'Update file')}   |   Size: {size_text}",
            font=("Tahoma", 13),
            text_color="#ded38d",
        ).pack(anchor="w", padx=18, pady=(0, 8))

        notes_text = (release.get("body") or asset.get("label") or "").strip()
        if not notes_text:
            notes_text = "The app will download the update, close, install it, and reopen automatically."

        notes = ctk.CTkTextbox(body, height=90, fg_color="#1c160e", text_color="#e8dcc0")
        notes.pack(fill="x", padx=18, pady=(0, 14))
        notes.insert("1.0", notes_text)
        notes.configure(state="disabled")

        self.status_label = ctk.CTkLabel(
            body,
            text="Ready to download.",
            font=("Tahoma", 14, "bold"),
            text_color="#e8dcc0",
        )
        self.status_label.pack(anchor="w", padx=18, pady=(0, 6))

        self.progress = ctk.CTkProgressBar(body)
        self.progress.pack(fill="x", padx=18, pady=(0, 6))
        self.progress.set(0)

        self.detail_label = ctk.CTkLabel(
            body,
            text="0%",
            font=("Tahoma", 13),
            text_color="#ded38d",
        )
        self.detail_label.pack(anchor="w", padx=18, pady=(0, 16))

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x", padx=18, pady=(8, 18))

        self.install_btn = ctk.CTkButton(
            buttons,
            text="Install Update",
            fg_color="#f5c400",
            text_color="#15100a",
            hover_color="#d9a900",
            command=self.start,
        )
        self.install_btn.pack(side="right", padx=(8, 0))

        self.cancel_btn = ctk.CTkButton(
            buttons,
            text="Later",
            fg_color="#3b2e1c",
            hover_color="#725a34",
            command=self.cancel,
        )
        self.cancel_btn.pack(side="right")

    def start(self):
        if self.started:
            return
        self.started = True
        self.install_btn.configure(state="disabled", text="Installing...")
        self.cancel_btn.configure(state="disabled")
        self.set_status("Starting download...", 0)
        threading.Thread(
            target=_download_and_prepare_update,
            args=(self.root, self.latest, self.asset, self),
            daemon=True,
        ).start()

    def cancel(self):
        if self.started:
            return
        self.win.destroy()

    def set_status(self, text, progress=None, detail=None):
        if not self.win.winfo_exists():
            return
        self.status_label.configure(text_color="#e8dcc0")
        self.detail_label.configure(text_color="#ded38d")
        self.status_label.configure(text=text)
        if progress is not None:
            self.progress.set(max(0, min(1, progress)))
        if detail is not None:
            self.detail_label.configure(text=detail)
        elif progress is not None:
            self.detail_label.configure(text=f"{int(progress * 100)}%")

    def show_error(self, text):
        if not self.win.winfo_exists():
            return
        self.status_label.configure(text="Update failed", text_color="#ff6b6b")
        self.detail_label.configure(text=text, text_color="#ffb4b4")
        self.install_btn.configure(state="normal", text="Try Again")
        self.cancel_btn.configure(state="normal", text="Close")
        self.started = False


def _format_bytes(value):
    try:
        size = float(value or 0)
    except Exception:
        size = 0
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024


def _on_download_progress(dialog, downloaded_bytes, total_bytes):
    if not dialog:
        return

    if total_bytes:
        progress = min(downloaded_bytes / total_bytes, 0.95)
        detail = (
            f"{int(progress * 100)}%  "
            f"({_format_bytes(downloaded_bytes)} / {_format_bytes(total_bytes)})"
        )
    else:
        progress = None
        detail = f"Downloaded {_format_bytes(downloaded_bytes)}"

    _update_dialog(dialog, "status", "Downloading update...", progress, detail)


def _update_dialog(dialog, kind, text, progress=None, detail=None):
    if not dialog:
        return

    def apply_update():
        if kind == "error":
            dialog.show_error(text)
        else:
            dialog.set_status(text, progress, detail)

    _run_on_ui(dialog.root, apply_update)


def _ask_to_install_update(root, latest, asset, release=None):
    if root is None or not root.winfo_exists():
        answer = messagebox.askyesno(
            "Update Available",
            f"Version {latest} is available.\n\n"
            "Install it now? The app will close, update itself, and reopen.",
        )
        if not answer:
            return
        threading.Thread(
            target=_download_and_prepare_update,
            args=(root, latest, asset, None),
            daemon=True,
        ).start()
        return

    _UpdateProgressDialog(root, latest, asset, release or {})


def _download_and_prepare_update(root, latest, asset, dialog=None):
    try:
        _update_dialog(dialog, "status", "Downloading update...", 0)
        downloaded = _download_asset(
            asset,
            lambda downloaded_bytes, total_bytes: _on_download_progress(
                dialog,
                downloaded_bytes,
                total_bytes,
            )
        )
        _update_dialog(dialog, "status", "Preparing update files...", 0.96)
        if downloaded.suffix.lower() == ".zip":
            script = _create_zip_update_script(downloaded)
        elif downloaded.suffix.lower() == ".exe":
            script = _create_exe_update_script(downloaded)
        else:
            raise RuntimeError(f"Unsupported update file: {downloaded.name}")

        _update_dialog(dialog, "status", "Ready to install. The app will restart...", 1)
        if root is not None and root.winfo_exists():
            _run_on_ui(root, lambda: root.after(
                900,
                lambda: _start_update_and_exit(root, latest, script)
            ))
        else:
            _start_update_and_exit(root, latest, script)
    except Exception as exc:
        print("Update install error:", exc)
        if dialog:
            _update_dialog(dialog, "error", f"Could not install the update:\n{exc}", None)
        else:
            _run_on_ui(root, lambda: messagebox.showerror(
                "Update Error",
                f"Could not install the update:\n{exc}",
            ))


def _download_asset(asset, progress_callback=None):
    url = asset.get("browser_download_url")
    name = asset.get("name") or "CafePOS-update"
    if not url:
        raise RuntimeError("Selected update asset does not have a download URL.")

    update_dir = Path(tempfile.gettempdir()) / "CafePOS_Update"
    update_dir.mkdir(parents=True, exist_ok=True)
    destination = update_dir / name

    with requests.get(url, stream=True, timeout=30) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length") or asset.get("size") or 0)
        downloaded = 0
        with destination.open("wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)

    return destination


def _create_exe_update_script(downloaded_exe):
    if not getattr(sys, "frozen", False):
        raise RuntimeError(
            "An .exe update can only replace a packaged Cafe POS executable."
        )

    app_exe = Path(sys.executable).resolve()
    return _write_batch_script(
        "install_cafepos_exe_update.bat",
        build_exe_update_commands(downloaded_exe, app_exe),
    )


def build_exe_update_commands(downloaded_exe, app_exe, max_attempts=30):
    """Build a self-replacing updater script with bounded lock retries."""
    downloaded_exe = Path(downloaded_exe)
    app_exe = Path(app_exe)
    error_log = app_exe.parent / "CafeRoom-update-error.log"
    return [
        "@echo off",
        "setlocal EnableDelayedExpansion",
        "set attempts=0",
        "timeout /t 2 /nobreak >nul",
        ":wait_for_app",
        f'move /y "{downloaded_exe}" "{app_exe}" >nul 2>nul',
        "if errorlevel 1 (",
        "  set /a attempts+=1",
        f"  if !attempts! GEQ {int(max_attempts)} goto update_failed",
        "  timeout /t 1 /nobreak >nul",
        "  goto wait_for_app",
        ")",
        f'start "" "{app_exe}"',
        "endlocal",
        'del "%~f0"',
        "exit /b 0",
        ":update_failed",
        f'echo CafeRoom could not replace the application after {int(max_attempts)} attempts.> "{error_log}"',
        f'echo Downloaded update: {downloaded_exe}>> "{error_log}"',
        f'echo Installed application: {app_exe}>> "{error_log}"',
        "endlocal",
        "exit /b 1",
    ]


def _create_zip_update_script(downloaded_zip):
    install_dir = _install_dir()
    staging_dir = Path(tempfile.gettempdir()) / "CafePOS_Update" / "staged"

    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(downloaded_zip) as archive:
        archive.extractall(staging_dir)

    source_dir = _find_zip_root(staging_dir)
    app_exe = Path(sys.executable).resolve() if getattr(sys, "frozen", False) else None
    restart_command = f'start "" "{app_exe}"' if app_exe else ""

    commands = [
        "@echo off",
        "setlocal",
        "timeout /t 2 /nobreak >nul",
    ]

    for item in source_dir.iterdir():
        if item.name in PROTECTED_FILES:
            continue

        target = install_dir / item.name
        if item.is_dir():
            commands.extend([
                f'xcopy "{item}" "{target}\\" /e /i /y >nul',
            ])
        else:
            commands.extend([
                f':copy_{_batch_label(item.name)}',
                f'copy /y "{item}" "{target}" >nul 2>nul',
                "if errorlevel 1 (",
                "  timeout /t 1 /nobreak >nul",
                f"  goto copy_{_batch_label(item.name)}",
                ")",
            ])

    if restart_command:
        commands.append(restart_command)

    commands.extend([
        f'rmdir /s /q "{staging_dir}"',
        "endlocal",
        'del "%~f0"',
    ])

    return _write_batch_script("install_cafepos_zip_update.bat", commands)


def _install_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _find_zip_root(staging_dir):
    children = list(staging_dir.iterdir())
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return staging_dir


def _batch_label(name):
    return "".join(char if char.isalnum() else "_" for char in name)


def _write_batch_script(name, lines):
    script = Path(tempfile.gettempdir()) / "CafePOS_Update" / name
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return script


def _start_update_and_exit(root, latest, script):
    subprocess.Popen(
        ["cmd", "/c", str(script)],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )

    if root is not None and root.winfo_exists():
        root.destroy()
    else:
        sys.exit(0)


def _run_on_ui(root, callback):
    if root is not None and root.winfo_exists():
        root.after(0, callback)
    else:
        callback()
