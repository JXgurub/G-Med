import json
import os
import time
import threading
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

try:
    if os.name == 'nt':
        import win32print
    else:
        win32print = None
except Exception:
    win32print = None


class GMedPrinterService:
    def __init__(self, config_path: str = 'config.json'):
        self.config_path = os.path.abspath(config_path)
        self.config = self._load_config()
        self.api_base_url = str(self.config.get('api_base_url', '')).rstrip('/')
        self.device_token = str(self.config.get('device_token', ''))
        self.clinic_id = str(self.config.get('clinic_id', ''))
        self.reception_room_id = str(self.config.get('reception_room_id', ''))
        self.service_name = str(self.config.get('service_name', 'GMedPrinterService'))
        self.printer_name_keywords = [
            str(item).lower() for item in self.config.get(
                'printer_name_contains',
                ['xp-80c', 'xprinter', 'xp-q200', 'thermal receipt'],
            )
        ]
        self.preferred_printer_name = str(self.config.get('preferred_printer_name', '')).strip()
        self.heartbeat_interval = int(self.config.get('heartbeat_interval_seconds', 20))
        self.poll_interval = int(self.config.get('poll_interval_seconds', 5))
        log_file = self.config.get('log_file', 'printer_service.log')
        if not os.path.isabs(log_file):
            log_file = os.path.join(os.path.dirname(self.config_path), log_file)
        self.log_file = os.path.abspath(log_file)
        self.printer_name = None
        self.printer_status = 'offline'
        self.service_online = True
        self._stop_event = threading.Event()

    def _load_config(self) -> Dict[str, Any]:
        config_path = os.path.abspath(self.config_path)
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Printer config not found: {config_path}. Copy config.example.json to config.json and fill values."
            )
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{timestamp}] {message}\n"
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception:
            print(line.strip())

    def _server_headers(self) -> Dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Device-Token': self.device_token,
        }

    def _api(self, method: str, url: str, payload: Optional[Dict[str, Any]] = None):
        if not self.api_base_url:
            raise RuntimeError('API base URL not configured')
        full_url = f"{self.api_base_url}{url}"
        try:
            resp = requests.request(
                method=method,
                url=full_url,
                headers=self._server_headers(),
                json=payload,
                timeout=15,
                verify=True,
            )
            return resp
        except requests.RequestException as exc:
            raise RuntimeError(f"API call failed: {exc}") from exc

    def detect_printers(self) -> List[str]:
        if os.name != 'nt' or win32print is None:
            self.log('Windows-only printer detection is not available in this environment.')
            return []

        try:
            printer_names = []
            enum_result = win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS,
                None,
                2,
            )
            if isinstance(enum_result, tuple) and len(enum_result) >= 3 and isinstance(enum_result[2], (list, tuple)):
                printers = enum_result[2]
            else:
                printers = enum_result

            for printer in printers:
                if isinstance(printer, dict):
                    name = str(printer.get('pPrinterName') or '').strip()
                elif isinstance(printer, (list, tuple)):
                    name = str(printer[2] if len(printer) > 2 else printer[0]).strip()
                else:
                    name = str(printer).strip()
                if name:
                    printer_names.append(name)
            return printer_names
        except Exception as exc:
            self.log(f"Printer scan error: {exc}")
            return []

    def find_xprinter(self) -> Optional[str]:
        printers = self.detect_printers()
        self.log(f'Windows printers detected: {printers}')
        if not printers:
            self.printer_status = 'disconnected'
            return None

        if self.preferred_printer_name:
            preferred_lower = self.preferred_printer_name.casefold()
            for printer_name in printers:
                if printer_name.casefold() == preferred_lower:
                    self.printer_name = printer_name
                    self.printer_status = 'ready'
                    return printer_name

        for printer_name in printers:
            lower_name = printer_name.lower()
            if any(keyword in lower_name for keyword in self.printer_name_keywords):
                self.printer_name = printer_name
                self.printer_status = 'ready'
                return printer_name

        if self.config.get('allow_default_printer', True):
            try:
                default_printer = str(win32print.GetDefaultPrinter() or '').strip()
            except Exception:
                default_printer = ''
            if default_printer and default_printer in printers:
                self.printer_name = default_printer
                self.printer_status = 'ready'
                self.log(f'Using Windows default printer: {default_printer}')
                return default_printer

        self.printer_status = 'disconnected'
        self.printer_name = None
        return None

    def printer_is_ready(self) -> bool:
        if os.name != 'nt':
            return False
        return self.find_xprinter() is not None

    def heartbeat(self) -> None:
        payload = {
            'service_online': True,
            'printer_connected': self.printer_is_ready(),
            'printer_name': self.printer_name,
            'printer_status': self.printer_status,
            'device_id': self.device_token,
            'clinic_id': self.clinic_id,
            'reception_room_id': self.reception_room_id,
            'last_seen': datetime.utcnow().isoformat() + 'Z',
            'service_name': self.service_name,
        }
        try:
            resp = self._api('POST', '/api/v1/printers/heartbeat/', payload)
            if resp.status_code >= 400:
                self.log(f"Heartbeat failed: {resp.status_code} {resp.text}")
        except Exception as exc:
            self.log(f"Heartbeat exception: {exc}")

    def fetch_pending_jobs(self) -> List[Dict[str, Any]]:
        try:
            resp = self._api(
                'GET',
                f"/api/v1/printers/jobs/pending/?device_token={self.device_token}&clinic_id={self.clinic_id}&reception_room_id={self.reception_room_id}",
            )
            if resp.status_code != 200:
                self.log(f"Fetch pending jobs failed: {resp.status_code} {resp.text}")
                return []
            data = resp.json()
            return data.get('jobs', []) if isinstance(data, dict) else []
        except Exception as exc:
            self.log(f"Fetch pending jobs error: {exc}")
            return []

    def build_espos_ticket(self, job: Dict[str, Any]) -> bytes:
        payload = job.get('payload', {}) or {}
        queue_number = str(payload.get('queue_number') or '').strip()
        queue_number_size = str(payload.get('queue_number_size') or 'large').strip().lower()
        lines = payload.get('lines', [])
        if lines:
            text = '\n'.join(lines)
        else:
            text = (
                '================================\n'
                '            G-MED\n'
                '      TEST CHOP ETISH\n'
                '================================\n\n'
                f"Klinika: {payload.get('clinic_name', 'N/A')}\n"
                f"Qabulxona: {payload.get('reception_room_name', 'N/A')}\n"
                f"Sana: {datetime.now().strftime('%d.%m.%Y')}\n"
                f"Vaqt: {datetime.now().strftime('%H:%M')}\n\n"
                'Printer muvaffaqiyatli ulangan.\n'
                '================================'
            )

        safe_text = text.replace('\r\n', '\n').replace('\r', '\n')
        lines_list = safe_text.split('\n')
        encoded_lines = []
        queue_number_line_index = None
        if queue_number:
            try:
                queue_number_line_index = lines_list.index(queue_number)
            except ValueError:
                queue_number_line_index = None

        for line_index, raw_line in enumerate(lines_list):
            line = raw_line.strip('\t')
            try:
                encoded_line = line.encode('cp866')
            except Exception:
                encoded_line = line.encode('utf-8', errors='ignore')
            encoded_lines.append((encoded_line, line_index == queue_number_line_index))

        output = b'\x1B\x40'
        output += b'\x1B\x74\x01'
        output += b'\x1B\x61\x01'
        output += b'\x1B\x21\x00'
        size_command = {
            'small': b'\x1B\x21\x01',
            'medium': b'\x1B\x21\x10',
            'large': b'\x1D\x21\x22',
        }.get(queue_number_size, b'\x1D\x21\x22')
        for line, is_queue_number in encoded_lines:
            if is_queue_number:
                output += size_command
            output += line + b'\n'
            if is_queue_number:
                output += b'\x1D\x21\x00'
        output += b'\n\x1B\x64\x0A\x1D\x56\x00'
        return output

    def print_to_printer(self, job: Dict[str, Any]) -> None:
        printer_name = self.find_xprinter()
        if not printer_name:
            raise RuntimeError('Xprinter topilmadi yoki ulangan emas.')

        if os.name != 'nt' or win32print is None:
            raise RuntimeError('Windows print subsystem mavjud emas. Lokal Windows kompyuterda ishlashi kerak.')

        try:
            hprinter = win32print.OpenPrinter(printer_name)
            win32print.StartDocPrinter(hprinter, 1, ('G-MED Printer Ticket', None, 'RAW'))
            win32print.StartPagePrinter(hprinter)
            data = self.build_espos_ticket(job)
            win32print.WritePrinter(hprinter, data)
            win32print.EndPagePrinter(hprinter)
            win32print.EndDocPrinter(hprinter)
            win32print.ClosePrinter(hprinter)
        except Exception as exc:
            raise RuntimeError(f'Printerga chop etishda xatolik: {exc}') from exc

    def update_job_status(self, job_id: str, status: str, error_message: Optional[str] = None) -> None:
        payload = {
            'status': status,
            'error_message': error_message,
            'device_id': self.device_token,
            'clinic_id': self.clinic_id,
            'reception_room_id': self.reception_room_id,
            'device_name': self.printer_name or 'unknown',
            'printed_at': datetime.utcnow().isoformat() + 'Z' if status == 'completed' else None,
        }
        try:
            resp = self._api('PATCH', f'/api/v1/printers/jobs/{job_id}/status/', payload)
            if resp.status_code >= 400:
                self.log(f"Status update failed for job {job_id}: {resp.status_code} {resp.text}")
        except Exception as exc:
            self.log(f"Status update error for job {job_id}: {exc}")

    def process_jobs(self) -> None:
        jobs = self.fetch_pending_jobs()
        for job in jobs:
            job_id = str(job.get('id', ''))
            if not job_id:
                continue

            try:
                self.update_job_status(job_id, 'printing')
                self.print_to_printer(job)
                self.update_job_status(job_id, 'completed')
                self.log(f"Job {job_id} completed successfully.")
            except Exception as exc:
                self.log(f"Job {job_id} failed: {exc}")
                self.update_job_status(job_id, 'failed', str(exc))

    def start(self) -> None:
        self.log('G-MED Printer Service started.')
        while not self._stop_event.is_set():
            try:
                self.heartbeat()
                self.process_jobs()
            except Exception as exc:
                self.log(f"Service loop error: {exc}")
            time.sleep(self.poll_interval)

    def stop(self) -> None:
        self._stop_event.set()
        self.log('G-MED Printer Service shutdown requested.')


if __name__ == '__main__':
    service = GMedPrinterService('config.json')
    try:
        service.start()
    except KeyboardInterrupt:
        service.stop()
        print('Interrupted by user.')
