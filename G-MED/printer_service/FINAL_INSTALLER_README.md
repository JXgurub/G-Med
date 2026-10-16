# G-MED Printer Service installer package

The one-click installer supports clinic and pharmacy printer setup. The clinic option preserves the existing clinic/reception authentication and service identity; the pharmacy option uses the pharmacy owner's login and installs an isolated pharmacy Windows service.

## Verified backend contract

The following backend functionality already exists and matches the clinic printer requirement:

- Device registration and token creation in [hospitoll_backend/apps/printers/views.py](../../hospitoll_backend/apps/printers/views.py)
- Device and print-job models in [hospitoll_backend/apps/printers/models.py](../../hospitoll_backend/apps/printers/models.py)
- Device status and printer health API in [hospitoll_backend/apps/printers/views.py](../../hospitoll_backend/apps/printers/views.py)
- Frontend reception printer panel in [hospitoll_frontend/src/pages/ReceptionDashboard.jsx](../../hospitoll_frontend/src/pages/ReceptionDashboard.jsx)

Relevant API flow:

- POST /api/v1/printers/register/
- POST /api/v1/printers/heartbeat/
- GET /api/v1/printers/jobs/pending/
- PATCH /api/v1/printers/jobs/{id}/status/
- GET /api/v1/printers/my-status/

The clinic endpoints and clinic data model remain unchanged. Pharmacy setup adds an authenticated registration endpoint and reuses the existing printer device and print-job models.

## Printer package folder structure

Copy the package folder to the appropriate clinic or pharmacy Windows computer:

- [G-MED/printer_service/config.json](./config.json)
- [G-MED/printer_service/config.example.json](./config.example.json)
- [G-MED/printer_service/printer_service.py](./printer_service.py)
- [G-MED/printer_service/windows_service.py](./windows_service.py)
- [G-MED/printer_service/install_windows_service.ps1](./install_windows_service.ps1)
- [G-MED/printer_service/build_one_click_installer.ps1](./build_one_click_installer.ps1)
- [G-MED/printer_service/one_click_installer.py](./one_click_installer.py)
- [G-MED/printer_service/requirements.txt](./requirements.txt)
- [G-MED/printer_service/README.md](./README.md)
- [G-MED/printer_service/uninstall_windows_service.ps1](./uninstall_windows_service.ps1)

## One-click installer build command

On the development machine, run:

```powershell
cd .\G-MED\printer_service
powershell -ExecutionPolicy Bypass -File .\build_one_click_installer.ps1
```

This generates a Windows EXE in the `dist_installer` folder.

## Clinic installation flow

1. Copy the whole `printer_service` folder to the clinic PC.
2. Open the generated installer EXE.
3. Select **Klinika**, then enter the clinic reception login and password.
4. Click Install and allow administrator privileges when Windows asks.
5. The installer registers the printer and installs the Windows Service named `G-MED Printer Service`.
6. Service startup mode is `Automatic`; after reboot, it restarts automatically.
7. The local service detects Xprinter XP-Q200 over USB and connects to the backend using the device token.

## Pharmacy installation flow

1. Copy the whole `printer_service` folder to the pharmacy Windows PC.
2. Open the generated installer EXE and select **Dorixona**.
3. Enter the G-MED pharmacy owner email and password.
4. Allow administrator privileges when Windows asks. The installer registers a pharmacy-specific printer token; the password is not saved.
5. The pharmacy printer runs as `GMedPharmacyPrinterService`; it does not stop or replace the clinic service.

## Service name and behavior

- Windows Service name: `GMedPrinterService`
- Display name: `G-MED Printer Service`
- Startup type: Automatic
- It sends a heartbeat to the backend and polls pending print jobs.
- It updates job status to `printing`, `completed`, or `failed`.
- It reports printer connectivity and printer name back to the server.

## Uninstall

On the clinic PC, run the uninstall script from the same folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_windows_service.ps1
```

This removes the Windows service and shuts it down cleanly.

## Important notes

- The clinic installer flow and `GMedPrinterService` identity remain unchanged.
- The pharmacy uses a separate `GMedPharmacyPrinterService`, executable location, config, and device token.
- The installer sends the pharmacy login only to the authenticated G-MED login API; it does not write the password to the service config.
- All production backend communication goes through the existing G-MED API and device-token contract.
- The real printer action remains local to the Windows computer and does not block the pharmacy sale flow.
