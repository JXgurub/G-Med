import json
import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    import win32service
    import win32serviceutil
else:
    win32service = None
    win32serviceutil = None

try:
    import requests
except Exception:
    requests = None


SERVICE_NAME = "GMedPrinterService"
DISPLAY_NAME = "G-MED Printer Service"
SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(os.path.abspath(sys.argv[0])) if getattr(sys, 'frozen', False) else SOURCE_DIR
RUNTIME_DIR = getattr(sys, '_MEIPASS', SOURCE_DIR)
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
WINDOWS_SERVICE_PATH = os.path.join(RUNTIME_DIR, "windows_service.py")
PACKAGED_SERVICE_EXE = os.path.join(RUNTIME_DIR, "GMedPrinterService.exe")
BUILD_DIR = os.path.join(APP_DIR, "build")
DIST_DIR = os.path.join(APP_DIR, "dist")
INSTALLER_EXE_NAME = "GMedPrinterInstaller.exe"
DEFAULT_API_BASE_URL = "https://g-med.uz"
LOGIN_API_PATH = "/api/v1/clinics/reception-staff/login/"
PRINTER_REGISTER_API_PATH = "/api/v1/printers/register/"


def is_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def relaunch_as_admin():
    try:
        import ctypes
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            " ".join(["\"" + os.path.abspath(__file__) + "\""]),
            None,
            1,
        )
    except Exception:
        pass
    raise SystemExit(0)


def run_cmd(args, cwd=None):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def ensure_config_valid():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"config.json not found: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    required = ["api_base_url", "device_token", "clinic_id"]
    missing = [key for key in required if not str(config.get(key, "")).strip()]
    if missing:
        raise ValueError(f"Missing config values: {', '.join(missing)}")

    return config


def write_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")


def build_service_exe():
    if not os.path.exists(PACKAGED_SERVICE_EXE):
        raise FileNotFoundError(
            "Bundled GMedPrinterService.exe topilmadi. Installer build scriptini qayta ishga tushiring."
        )

    exe_path = os.path.join(DIST_DIR, "GMedPrinterService.exe")
    os.makedirs(DIST_DIR, exist_ok=True)
    shutil.copy2(PACKAGED_SERVICE_EXE, exe_path)

    if os.path.exists(CONFIG_PATH):
        shutil.copy2(CONFIG_PATH, os.path.join(DIST_DIR, "config.json"))
    return exe_path


def normalize_api_base_url(raw_value):
    value = str(raw_value or '').strip()
    if not value:
        return DEFAULT_API_BASE_URL.rstrip('/')

    value = value.strip().rstrip('/')
    if '://' not in value:
        value = 'https://' + value

    parsed = urlsplit(value)
    host = parsed.netloc or parsed.path
    if not host:
        return DEFAULT_API_BASE_URL.rstrip('/')

    cleaned_host = host.split('/')[0].strip()
    if not cleaned_host:
        return DEFAULT_API_BASE_URL.rstrip('/')

    scheme = parsed.scheme or 'https'
    return f"{scheme}://{cleaned_host}".rstrip('/')


def build_login_api_url(raw_value):
    base_url = normalize_api_base_url(raw_value)
    return base_url + LOGIN_API_PATH


def read_json_error(response):
    try:
        payload = response.json()
        if isinstance(payload, dict):
            return payload.get('detail') or payload.get('message') or payload.get('error') or json.dumps(payload, ensure_ascii=False)
    except Exception:
        pass
    return response.text.strip() or f"HTTP {response.status_code}"


def login_to_backend(api_base_url, email, password):
    if requests is None:
        raise RuntimeError("Python requests library is not available.")
    base_url = normalize_api_base_url(api_base_url)
    api_url = build_login_api_url(base_url)
    try:
        response = requests.post(api_url, json={"email": email, "password": password}, timeout=20)
    except requests.RequestException as exc:
        raise RuntimeError(f"G-MED serveriga ulanishda xatolik: {exc}") from exc

    if response.status_code == 404:
        raise RuntimeError(
            "G-MED login API topilmadi. Bu 404 xatosi backend host yoki API yo‘li noto‘g‘ri bo‘lganda chiqadi. "
            "Qaysi URLni kiritishingiz kerak: faqat asosiy host, masalan https://g-med.uz . "
            "https://g-med.uz/reception-login kabi frontend sahifa URLini kiritmang. "
            f"To‘g‘ri endpoint: {base_url}{LOGIN_API_PATH}"
        )

    if response.status_code != 200:
        detail = read_json_error(response)
        if detail:
            raise RuntimeError(detail)
        raise RuntimeError(f"Login failed: HTTP {response.status_code}. URL yoki server konfiguratsiyasi noto‘g‘ri bo‘lishi mumkin.")

    payload = response.json()
    token = payload.get("token")
    staff = payload.get("staff") or {}
    if not token:
        raise RuntimeError("Serverdan token keldi, lekin token bo‘sh edi.")
    clinic_id = staff.get("clinic") or staff.get("clinic_id")
    if not clinic_id:
        raise RuntimeError("Klinika ma’lumoti serverdan kelmadi. Reception staff login ma’lumotlari to‘liq emas.")
    return token, clinic_id, staff


def register_printer(api_base_url, reception_token, clinic_id):
    if requests is None:
        raise RuntimeError("Python requests library is not available.")
    base_url = normalize_api_base_url(api_base_url)
    api_url = base_url + PRINTER_REGISTER_API_PATH
    payload = {
        "clinic_id": str(clinic_id),
    }
    response = requests.post(
        api_url,
        headers={"X-Reception-Session": reception_token},
        json=payload,
        timeout=25,
    )
    if response.status_code != 200:
        detail = read_json_error(response)
        raise RuntimeError(detail or f"Printer registration failed: HTTP {response.status_code}")
    return response.json()


def install_service(exe_path):
    if not os.path.exists(exe_path):
        raise FileNotFoundError(f"Service EXE not found: {exe_path}")

    try:
        import win32service
    except Exception as exc:
        raise RuntimeError(f"Windows service modullari yuklanmadi: {exc}") from exc

    exe_path = os.path.abspath(exe_path)
    if not os.path.isfile(exe_path):
        raise FileNotFoundError(f"Service EXE topilmadi: {exe_path}")
    os.makedirs(os.path.dirname(exe_path), exist_ok=True)

    try:
        import win32serviceutil
        win32serviceutil.StopService(SERVICE_NAME)
    except Exception:
        pass
    try:
        win32serviceutil.RemoveService(SERVICE_NAME)
    except Exception:
        pass

    try:
        manager = win32service.OpenSCManager(
            None,
            None,
            win32service.SC_MANAGER_ALL_ACCESS,
        )
        try:
            service_handle = win32service.CreateService(
                manager,
                SERVICE_NAME,
                DISPLAY_NAME,
                win32service.SERVICE_ALL_ACCESS,
                win32service.SERVICE_WIN32_OWN_PROCESS,
                win32service.SERVICE_AUTO_START,
                win32service.SERVICE_ERROR_NORMAL,
                f'"{exe_path}"',
                None,
                0,
                None,
                None,
                None,
            )
            try:
                win32service.ChangeServiceConfig2(
                    service_handle,
                    win32service.SERVICE_CONFIG_DESCRIPTION,
                    "Local Windows printer polling service for G-MED queue tickets",
                )
            finally:
                win32service.CloseServiceHandle(service_handle)
        finally:
            win32service.CloseServiceHandle(manager)

        service_manager = win32service.OpenSCManager(
            None,
            None,
            win32service.SC_MANAGER_CONNECT,
        )
        try:
            service_handle = win32service.OpenService(
                service_manager,
                SERVICE_NAME,
                win32service.SERVICE_START | win32service.SERVICE_QUERY_STATUS,
            )
            try:
                win32service.StartService(service_handle, None)
            finally:
                win32service.CloseServiceHandle(service_handle)
        finally:
            win32service.CloseServiceHandle(service_manager)
    except Exception as exc:
        raise RuntimeError(f"Windows service o'rnatish/ishga tushirishda xatolik: {exc}\nYo'l: {exe_path}") from exc

    return True


class InstallerApp:
    def __init__(self, root):
        self.root = root
        root.title("G-MED Printer Service Setup")
        root.geometry("620x400")
        root.resizable(False, False)

        tk.Label(root, text="G-MED Printer Service", font=("Segoe UI", 16, "bold")).pack(pady=(18, 8))
        tk.Label(root, text="Klinikada printer avtomatik o‘rnatiladi. G-MED login orqali nazorati amalga oshiriladi.", wraplength=560, justify="center").pack(padx=20, pady=(0, 8))

        self.api_url_var = tk.StringVar(value=DEFAULT_API_BASE_URL)
        self.email_var = tk.StringVar(value="")
        self.password_var = tk.StringVar(value="")

        form = tk.Frame(root, padx=18, pady=8)
        form.pack(fill="x")

        tk.Label(form, text="G-MED asosiy host URL", anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=6)
        tk.Entry(form, textvariable=self.api_url_var, width=42).grid(row=0, column=1, sticky="ew", pady=6)

        tk.Label(form, text="Email", anchor="w").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=6)
        tk.Entry(form, textvariable=self.email_var, width=42).grid(row=1, column=1, sticky="ew", pady=6)

        tk.Label(form, text="Parol", anchor="w").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=6)
        tk.Entry(form, textvariable=self.password_var, width=42, show="*").grid(row=2, column=1, sticky="ew", pady=6)

        form.columnconfigure(1, weight=1)

        self.status = tk.StringVar(value="Tayyor")
        tk.Label(root, textvariable=self.status, fg="darkgreen", font=("Segoe UI", 10, "bold"), wraplength=560, justify="center").pack(pady=(8, 0))

        self.install_btn = tk.Button(root, text="O'rnatish", width=22, height=2, command=self.install)
        self.install_btn.pack(pady=(12, 0))

    def install(self):
        try:
            if not is_admin():
                self.status.set("Administrator huquqi so‘ralmoqda...")
                self.root.update()
                relaunch_as_admin()
                return

            raw_url = self.api_url_var.get().strip() or DEFAULT_API_BASE_URL
            api_base_url = normalize_api_base_url(raw_url)
            email = self.email_var.get().strip()
            password = self.password_var.get()
            if not email or not password:
                raise ValueError("Email va parolni kiriting.")

            self.status.set("G-MED login tekshirilmoqda...")
            self.root.update()
            self.status.set(f"Backend tekshirilmoqda: {build_login_api_url(api_base_url)}")
            self.root.update()
            reception_token, clinic_id, staff = login_to_backend(api_base_url, email, password)

            self.status.set("Printer ro‘yxatdan o‘tkazilmoqda...")
            self.root.update()
            registration = register_printer(api_base_url, reception_token, clinic_id)
            device_token = registration.get("device_token") or registration.get("deviceToken")
            if not device_token:
                raise RuntimeError("Server printer tokenini yaratmadi.")

            config = {
                "api_base_url": api_base_url,
                "device_token": device_token,
                "clinic_id": str(clinic_id),
                "reception_room_id": str(registration.get("reception_room_id") or ""),
                "service_name": SERVICE_NAME,
                "heartbeat_interval_seconds": 20,
                "poll_interval_seconds": 5,
                "printer_name_contains": ["xp-80c", "xprinter", "xp-q200", "xp-q200ii", "xprinter xp", "thermal receipt"],
                "preferred_printer_name": "XP-80C",
                "allow_default_printer": True,
                "log_file": os.path.join(DIST_DIR, "printer_service.log"),
            }
            write_config(config)

            self.status.set("Windows xizmatini yaratilmoqda...")
            self.root.update()
            exe_path = build_service_exe()

            self.status.set("Printer Service o‘rnatilmoqda...")
            self.root.update()
            install_service(exe_path)

            self.status.set("Muvaffaqiyatli o‘rnatildi. Service ishlayapti.")
            self.root.update()
            messagebox.showinfo(
                "Muvaffaqiyatli",
                "Printer Service o‘rnatildi.\n\n"
                "- G-MED login muvaffaqiyatli tekshirildi\n"
                "- Printer qurilmasi ro‘yxatdan o‘tkazildi\n"
                "- config.json avtomatik yozildi\n"
                "- Service Automatic rejimida o‘rnatildi\n"
                "- Tizim qayta ishga tushganda avtomatik start bo‘ladi",
            )
        except Exception as exc:
            self.status.set("O‘rnatishda xatolik")
            self.root.update()
            messagebox.showerror("Xatolik", str(exc))


def main():
    root = tk.Tk()
    InstallerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
