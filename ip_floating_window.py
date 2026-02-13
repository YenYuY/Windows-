import socket
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from urllib.error import URLError
from urllib.request import urlopen


REFRESH_SECONDS = 30
PUBLIC_IP_URL = "https://api.ipify.org?format=text"


def get_local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    finally:
        sock.close()


def get_public_ip(timeout: float = 4.0) -> str:
    with urlopen(PUBLIC_IP_URL, timeout=timeout) as response:
        return response.read().decode("utf-8").strip()


class IPFloatingWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("IP 懸浮視窗")
        self.geometry("320x170+40+40")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        try:
            self.wm_attributes("-toolwindow", True)
        except tk.TclError:
            pass

        self.local_ip = tk.StringVar(value="讀取中...")
        self.public_ip = tk.StringVar(value="讀取中...")
        self.status = tk.StringVar(value="初始化中...")
        self.keep_topmost = tk.BooleanVar(value=True)
        self._refreshing = False

        self._build_ui()
        self.refresh_ips()
        self.after(REFRESH_SECONDS * 1000, self._schedule_refresh)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="Local IP").grid(row=0, column=0, sticky="w")
        ttk.Label(root, textvariable=self.local_ip).grid(
            row=0, column=1, sticky="w", padx=(8, 0)
        )

        ttk.Label(root, text="Public IP").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(root, textvariable=self.public_ip).grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0)
        )

        btns = ttk.Frame(root)
        btns.grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))
        ttk.Button(btns, text="立即更新", command=self.refresh_ips).pack(side="left")
        ttk.Checkbutton(
            btns, text="置頂", variable=self.keep_topmost, command=self._toggle_topmost
        ).pack(side="left", padx=(10, 0))

        ttk.Label(root, textvariable=self.status, foreground="#555555").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )

    def _toggle_topmost(self) -> None:
        self.attributes("-topmost", self.keep_topmost.get())

    def _schedule_refresh(self) -> None:
        self.refresh_ips()
        self.after(REFRESH_SECONDS * 1000, self._schedule_refresh)

    def refresh_ips(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        self.status.set("更新中...")
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self) -> None:
        try:
            local_ip = get_local_ip()
        except OSError:
            local_ip = "讀取失敗"

        try:
            public_ip = get_public_ip()
        except (URLError, OSError, TimeoutError):
            public_ip = "讀取失敗"

        now = datetime.now().strftime("%H:%M:%S")
        self.after(0, lambda: self._apply_result(local_ip, public_ip, now))

    def _apply_result(self, local_ip: str, public_ip: str, now: str) -> None:
        self.local_ip.set(local_ip)
        self.public_ip.set(public_ip)
        self.status.set(f"最後更新: {now}（每 {REFRESH_SECONDS} 秒自動刷新）")
        self._refreshing = False


def main() -> None:
    app = IPFloatingWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
