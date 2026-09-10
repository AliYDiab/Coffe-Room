import customtkinter as ctk
from threading import Thread
import subprocess
import time
import requests
import tkinter as tk

import qrcode
from PIL import Image, ImageTk

from adb import init_db
from modules.cashier import show_cashier
from modules.receipts import show_receipts
from modules.analytics import show_analytics
from modules.inventory import show_inventory
from modules.ingredients import show_ingredients

from scanner_server import run_server


# =========================================================
# INIT DB
# =========================================================
init_db()

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


# =========================================================
# START FLASK SERVER
# =========================================================
def start_server():
    Thread(target=run_server, daemon=True).start()


# =========================================================
# START NGROK
# =========================================================
def start_ngrok():
    subprocess.Popen(
        ["ngrok", "http", "5000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


# =========================================================
# GET NGROK URL
# =========================================================
def get_ngrok_url():
    time.sleep(2)

    try:
        r = requests.get("http://127.0.0.1:4040/api/tunnels")
        data = r.json()

        for t in data["tunnels"]:
            if t["proto"] == "https":
                return t["public_url"]
    except requests.RequestException:
        return None

    return None


# =========================================================
# QR WINDOW
# =========================================================
def show_qr_window(url):

    win = tk.Tk()
    win.title("CoffeeRoom Scanner")
    win.geometry("420x520")
    win.configure(bg="#111827")

    tk.Label(
        win,
        text="📡 Scan to Open POS",
        font=("Arial", 18, "bold"),
        fg="white",
        bg="#111827"
    ).pack(pady=20)

    qr = qrcode.make(url)
    qr = qr.resize((280, 280))

    img = ImageTk.PhotoImage(qr)

    label = tk.Label(win, image=img, bg="#111827")
    label.image = img
    label.pack(pady=10)

    tk.Label(
        win,
        text=url,
        fg="#22c55e",
        bg="#111827"
    ).pack(pady=10)

    win.mainloop()


# =========================================================
# MAIN APP
# =========================================================
def main():

    # 1. Start backend
    start_server()
    start_ngrok()

    url = get_ngrok_url()

    if url:
        print("NGROK:", url)
        show_qr_window(url)

    # =====================================================
    # 2. START POS (ONLY ONE ROOT)
    # =====================================================
    root = ctk.CTk()
    root.title("☕ Café POS")
    root.attributes("-fullscreen", True)

    main_frame = ctk.CTkFrame(root)
    main_frame.pack(fill="both", expand=True)

    # =====================================================
    # NAVBAR
    # =====================================================
    top = ctk.CTkFrame(root)
    top.pack(fill="x")

    nav = ctk.CTkFrame(top, fg_color="transparent")
    nav.pack(fill="x", padx=10, pady=5)

    def nav_button(text, cmd):
        return ctk.CTkButton(
            nav,
            text=text,
            command=cmd,
            width=120,
            height=40,
            corner_radius=10
        )

    def refresh():
        show_cashier(main_frame, refresh)

    nav_button("كاشير", lambda: show_cashier(main_frame, refresh)).pack(side="left", padx=5)
    nav_button("فواتير", lambda: show_receipts(main_frame)).pack(side="left", padx=5)
    nav_button("بيانات", lambda: show_analytics(main_frame)).pack(side="left", padx=5)
    nav_button("المخزن", lambda: show_inventory(main_frame, refresh)).pack(side="left", padx=5)
    nav_button("مكونات", lambda: show_ingredients(main_frame)).pack(side="left", padx=5)

    # load default screen
    refresh()

    root.mainloop()


# =========================================================
# RUN
# =========================================================
if __name__ == "__main__":
    main()