import os
import sys
import threading
import time
import traceback

try:
    import win32event
    import win32service
    import win32serviceutil
    import servicemanager
except Exception:
    win32event = None
    win32service = None
    win32serviceutil = None
    servicemanager = None

from printer_service import GMedPrinterService


def _service_base_dir():
    executable = sys.executable if getattr(sys, 'frozen', False) else __file__
    return os.path.dirname(os.path.abspath(executable))


def _write_startup_error(message):
    try:
        with open(os.path.join(_service_base_dir(), 'service_startup.log'), 'a', encoding='utf-8') as log_file:
            log_file.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} {message}\n')
    except Exception:
        pass


class GMedPrinterWindowsService(win32serviceutil.ServiceFramework if win32serviceutil else object):
    _svc_name_ = 'GMedPrinterService'
    _svc_display_name_ = 'G-MED Printer Service'
    _svc_description_ = 'Local Windows service for printing reception queue tickets on Xprinter thermal printers.'

    def __init__(self, args):
        if win32serviceutil:
            super().__init__(args)

        base_dir = _service_base_dir()
        config_path = os.path.join(base_dir, 'config.json')
        try:
            self.service = GMedPrinterService(config_path)
        except Exception as exc:
            _write_startup_error(f'Initialization failed: {exc}\n{traceback.format_exc()}')
            raise
        self.stop_event = win32event.CreateEvent(None, 0, 0, None) if win32event else None
        self.worker = None
        self._shutdown_requested = threading.Event()

    def SvcStop(self):
        self._shutdown_requested.set()
        if self.service:
            self.service.stop()
        if self.stop_event:
            win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        if win32event is None:
            raise RuntimeError('win32event is not available on this machine.')

        self.worker = threading.Thread(target=self.service.start, daemon=True)
        self.worker.start()

        while not self._shutdown_requested.is_set():
            if self.service._stop_event.is_set():
                break
            win32event.WaitForSingleObject(self.stop_event, 500)

        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=3)


if __name__ == '__main__':
    if os.name != 'nt' or win32serviceutil is None:
        print('This Windows Service file is intended to run on Windows only.')
        sys.exit(1)

    if len(sys.argv) == 1 and servicemanager is not None:
        try:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(GMedPrinterWindowsService)
            servicemanager.StartServiceCtrlDispatcher()
        except Exception as exc:
            _write_startup_error(f'Service dispatcher failed: {exc}\n{traceback.format_exc()}')
            raise
    else:
        win32serviceutil.HandleCommandLine(GMedPrinterWindowsService)