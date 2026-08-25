# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['win32event', 'win32service', 'win32serviceutil', 'servicemanager', 'win32timezone', 'pywintypes', 'pythoncom', 'win32api', 'win32con']
hiddenimports += collect_submodules('win32')


a = Analysis(
    ['C:/Hospitoll/G-MED/printer_service/windows_service.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/Hospitoll/G-MED/printer_service/printer_service.py', '.')],
    hiddenimports=hiddenimports,
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
    name='GMedPrinterService',
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
