# G-MED Printer Service: clinic package

This is the final clinic-ready package for the local Windows printer service.

## 1. What to copy to the clinic PC

Copy the entire folder below to the clinic computer:

- G-MED/printer_service/

Inside that folder, keep all of these files together:

- config.json
- config.example.json
- printer_service.py
- windows_service.py
- one_click_installer.py
- build_one_click_installer.ps1
- install_windows_service.ps1
- uninstall_windows_service.ps1
- requirements.txt
- README.md
- dist_installer/GMedPrinterInstaller.exe

The installer EXE is generated in:

- G-MED/printer_service/dist_installer/GMedPrinterInstaller.exe

## 2. Important rule

Do not split the package.
Do not move only the EXE.
Do not delete the supporting files from the same folder.

The installer expects the full package to remain together.

## 3. Final deployment order

### Step 1: copy the whole folder

Copy the full folder to the clinic PC, for example:

- C:\G-MED\printer_service\

### Step 2: run the EXE

Double-click:

- C:\G-MED\printer_service\dist_installer\GMedPrinterInstaller.exe

### Step 3: enter login data

The installer opens a simple UI.
The clinic employee enters:

- G-MED URL
- reception email
- password

### Step 4: installer does the setup

The installer automatically:

- logs in to the backend
- resolves the clinic and staff
- registers the local printer device
- creates the device token
- writes config.json
- builds the Windows service EXE
- installs the service as G-MED Printer Service
- starts the service in Automatic mode

### Step 5: service starts in background

The service then:

- sends heartbeat to the backend
- checks for pending print jobs
- detects Xprinter XP-Q200
- sets printer status ready or offline
- updates job status to printing/completed/failed

## 4. Expected service name in Windows Services

- Service name: GMedPrinterService
- Display name: G-MED Printer Service
- Startup type: Automatic

## 5. Recommended clinic flow

The employee should do only this:

1. Copy the package to the clinic PC
2. Open the EXE
3. Enter login and password
4. Click Install
5. Allow administrator permission when prompted
6. Wait for success message
7. The service starts by itself

No Python, no pip, no PowerShell, no CMD required.

## 6. Safe real-world checklist before leaving the clinic

Before leaving the clinic, verify:

- Windows Services shows G-MED Printer Service
- service status is Running
- printer is connected physically to USB
- token registration succeeded in the backend
- config.json contains real values
- heartbeat is being sent
- the test print works

## 7. If installation fails

Check the following in order:

1. Windows asked for admin rights and was accepted
2. the user entered the correct reception email/password
3. the clinic is active and reception staff is valid
4. backend URL is reachable
5. service remains in Automatic mode
6. the printer is physically connected and recognized by Windows

## 8. Final note

This package is designed for the clinic deployment flow: one EXE, one login, one automatic installation, and no manual terminal work.
