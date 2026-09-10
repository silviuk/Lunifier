# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

datas = [('lunifier/resources', 'lunifier/resources')]
binaries = []
hiddenimports = []

# Collect CustomTkinter assets and theme json files
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# Collect pystray
tmp_pystray = collect_all('pystray')
datas += tmp_pystray[0]
binaries += tmp_pystray[1]
hiddenimports += tmp_pystray[2]

# Collect pynput
tmp_pynput = collect_all('pynput')
datas += tmp_pynput[0]
binaries += tmp_pynput[1]
hiddenimports += tmp_pynput[2]

excludes = [
    'tkinter.test',
    'unittest',
    'email',
    'html',
    'http',
    'xmlrpc',
    'pydoc',
    'doctest',
    'test',
    'distutils',
    'setuptools',
    'pip',
    'sqlite3',
    'multiprocessing.test',
    'lib2to3',
]

a = Analysis(
    ['run_lunifier.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=2,
)

# Filter out bloated and unnecessary Tcl/Tk data files (tzdata has 630 files, msgs has 145 files)
clean_datas = []
for item in a.datas:
    dest = item[0].replace('\\', '/')
    if any(skip in dest for skip in [
        '_tcl_data/tzdata',
        '_tcl_data/msgs',
        '_tk_data/msgs',
        '_tk_data/demos',
        'customtkinter/assets/icons'
    ]):
        continue
    clean_datas.append(item)
a.datas = clean_datas

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Lunifier',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='lunifier/resources/icon.ico',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Lunifier',
)
