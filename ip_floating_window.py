import ipaddress
import os
import re
import socket
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from urllib.error import URLError
from urllib.request import urlopen


REFRESH_SECONDS = 30
PUBLIC_IP_URL = "https://api.ipify.org?format=text"


def _should_keep_ip_line(key: str) -> bool:
    key_lower = key.lower()
    include_markers = ["ipv4", "ipv6", "ip address", "ip 位址", "ip位址", "位址", "地址"]
    exclude_markers = [
        "physical",
        "mac",
        "mask",
        "gateway",
        "dns",
        "dhcp",
        "wins",
        "lease",
        "prefix",
        "實體",
        "子網路",
        "閘道",
        "遮罩",
    ]
    if any(marker in key_lower for marker in exclude_markers):
        return False
    if any(marker in key_lower for marker in include_markers):
        return True
    return any(marker in key for marker in ["位址", "地址"])


def _extract_valid_ips(raw_value: str) -> list[str]:
    candidates = re.split(r"\s+", raw_value.strip())
    found: list[str] = []

    for token in candidates:
        token = token.strip("[](),;")
        token = token.split("(")[0]
        if "%" in token:
            token = token.split("%", 1)[0]
        if not token:
            continue
        try:
            parsed = ipaddress.ip_address(token)
        except ValueError:
            continue
        addr = str(parsed)
        if addr not in found:
            found.append(addr)

    return found


def _parse_windows_ipconfig(output: str) -> dict[str, list[str]]:
    interfaces: dict[str, list[str]] = {}
    current_name: str | None = None

    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        # Section headers are not indented in ipconfig output.
        if raw_line and not raw_line[0].isspace():
            if line.endswith(":"):
                current_name = line[:-1].strip()
                interfaces.setdefault(current_name, [])
            else:
                current_name = None
            continue

        if not current_name or ":" not in line:
            continue

        key, value = line.strip().split(":", 1)
        if not _should_keep_ip_line(key):
            continue

        for ip_value in _extract_valid_ips(value):
            if ip_value not in interfaces[current_name]:
                interfaces[current_name].append(ip_value)

    return {name: ips for name, ips in interfaces.items() if ips}


def _get_default_local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    finally:
        sock.close()


def get_all_interface_ips() -> dict[str, list[str]]:
    if os.name == "nt":
        result = subprocess.run(["ipconfig"], capture_output=True, text=False)
        if result.returncode == 0 and result.stdout:
            parsed_output = ""
            for encoding in ("utf-8", "cp950", "big5", "mbcs"):
                try:
                    parsed_output = result.stdout.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if not parsed_output:
                parsed_output = result.stdout.decode("utf-8", errors="ignore")
            if parsed_output.strip():
                return _parse_windows_ipconfig(parsed_output)

    # Fallback when not on Windows or ipconfig parsing failed.
    try:
        return {"Default Interface": [_get_default_local_ip()]}
    except OSError:
        return {}


def get_public_ip(timeout: float = 4.0) -> str:
    with urlopen(PUBLIC_IP_URL, timeout=timeout) as response:
        return response.read().decode("utf-8").strip()


class IPFloatingWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("IP 懸浮視窗")
        self.geometry("520x380+40+40")
        self.minsize(420, 280)
        self.resizable(True, True)
        self.attributes("-topmost", True)
        try:
            self.wm_attributes("-toolwindow", True)
        except tk.TclError:
            pass

        self.public_ip = tk.StringVar(value="讀取中...")
        self.status = tk.StringVar(value="初始化中...")
        self.keep_topmost = tk.BooleanVar(value=True)
        self._refreshing = False
        self.interfaces_box: tk.Text | None = None

        self._build_ui()
        self.refresh_ips()
        self.after(REFRESH_SECONDS * 1000, self._schedule_refresh)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(4, weight=1)

        ttk.Label(root, text="目前出口 Public IP").grid(row=0, column=0, sticky="w")
        ttk.Label(root, textvariable=self.public_ip).grid(
            row=1, column=0, sticky="w", pady=(4, 8)
        )

        ttk.Separator(root, orient="horizontal").grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(root, text="所有介面 IP（含 VPN）").grid(row=3, column=0, sticky="w")

        list_frame = ttk.Frame(root)
        list_frame.grid(row=4, column=0, sticky="nsew", pady=(6, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.interfaces_box = tk.Text(list_frame, height=10, wrap="none")
        self.interfaces_box.grid(row=0, column=0, sticky="nsew")
        self.interfaces_box.configure(state="disabled")

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.interfaces_box.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.interfaces_box.configure(yscrollcommand=scrollbar.set)

        btns = ttk.Frame(root)
        btns.grid(row=5, column=0, sticky="w", pady=(10, 0))
        ttk.Button(btns, text="立即更新", command=self.refresh_ips).pack(side="left")
        ttk.Checkbutton(
            btns, text="置頂", variable=self.keep_topmost, command=self._toggle_topmost
        ).pack(side="left", padx=(10, 0))

        ttk.Label(root, textvariable=self.status, foreground="#555555").grid(
            row=6, column=0, sticky="w", pady=(10, 0)
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
        all_interface_ips = get_all_interface_ips()

        try:
            public_ip = get_public_ip()
        except (URLError, OSError, TimeoutError):
            public_ip = "讀取失敗"

        now = datetime.now().strftime("%H:%M:%S")
        self.after(0, lambda: self._apply_result(all_interface_ips, public_ip, now))

    def _apply_result(self, all_interface_ips: dict[str, list[str]], public_ip: str, now: str) -> None:
        self.public_ip.set(public_ip)
        self._set_interfaces_text(all_interface_ips)
        self.status.set(f"最後更新: {now}（每 {REFRESH_SECONDS} 秒自動刷新）")
        self._refreshing = False

    def _set_interfaces_text(self, all_interface_ips: dict[str, list[str]]) -> None:
        if self.interfaces_box is None:
            return

        if not all_interface_ips:
            content = "找不到可用的介面 IP。"
        else:
            rows: list[str] = []
            for interface_name, ips in all_interface_ips.items():
                rows.append(f"[{interface_name}]")
                for ip_value in ips:
                    rows.append(f"  - {ip_value}")
                rows.append("")
            content = "\n".join(rows).rstrip()

        self.interfaces_box.configure(state="normal")
        self.interfaces_box.delete("1.0", tk.END)
        self.interfaces_box.insert("1.0", content)
        self.interfaces_box.configure(state="disabled")


def main() -> None:
    app = IPFloatingWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
