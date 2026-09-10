from flask import Flask, request, jsonify, send_from_directory
from threading import Thread
import os
import sys
import time

# =========================
# PyInstaller-safe path
# =========================
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

STATIC_FOLDER = os.path.join(BASE_DIR, "static")

app = Flask(__name__, static_folder=STATIC_FOLDER)

handle_scan_callback = None


# =========================
# ANTI-DUPLICATE SCAN FIX
# =========================
last_scan = {
    "code": None,
    "time": 0
}

SCAN_COOLDOWN = 1.0  # 1 second protection


# =========================
# HOME PAGE
# =========================
@app.route("/")
def home():
    return send_from_directory(STATIC_FOLDER, "SCANNER.html")


# =========================
# RECEIVE SCAN
# =========================
@app.route("/scan", methods=["POST"])
def scan():

    data = request.get_json()

    code = (data.get("code", "") or "").strip()

    if not code:
        return jsonify({"status": "empty"})

    now = time.time()

    # =========================
    # DUPLICATE PROTECTION
    # =========================
    if last_scan["code"] == code and (now - last_scan["time"]) < SCAN_COOLDOWN:
        print("🚫 DUPLICATE IGNORED:", code)
        return jsonify({"status": "duplicate_ignored"})

    last_scan["code"] = code
    last_scan["time"] = now

    print("📦 SCAN:", code)

    # send to cashier
    try:
        handle_scan_callback(code)
    except Exception as exc:
        print(f"[ERROR] scan callback failed: {exc}")
        return jsonify({"status": "callback_error"}), 500

    return jsonify({"status": "ok"})


# =========================
# RUN SERVER
# =========================
def run_server():
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False
    )


# =========================
# START SERVER THREAD
# =========================
def start_scanner_server(callback):

    global handle_scan_callback
    handle_scan_callback = callback

    thread = Thread(
        target=run_server,
        daemon=True
    )

    thread.start()