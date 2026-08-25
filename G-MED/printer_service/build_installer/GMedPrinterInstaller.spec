# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/Hospitoll/G-MED/printer_service/one_click_installer.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/Hospitoll/G-MED/printer_service/windows_service.py', '.'), ('C:/Hospitoll/G-MED/printer_service/printer_service.py', '.'), ('C:/Hospitoll/G-MED/printer_service/service_build_dist/GMedPrinterService.exe', '.')],
    hiddenimports=['win32service', 'win32serviceutil', 'win32api', 'win32con', 'pywintypes', 'pythoncom', 'servicemanager'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GMedPrinterInstaller',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
