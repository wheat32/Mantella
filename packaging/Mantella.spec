# PyInstaller spec for Mantella.exe (one-folder build). Run via packaging/build_mod_archive.py
# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

project_root = os.path.abspath(os.path.join(SPECPATH, '..'))

datas = []
binaries = []
hiddenimports = ['tiktoken_ext', 'tiktoken_ext.openai_public', 'pkg_resources', 'win32gui', 'win32api', 'win32con']

# Packages that load their own data files (web UI assets, bundled models, tokenizers, audio libraries) at runtime
for package in ['gradio', 'gradio_client', 'faster_whisper', 'moonshine_onnx', 'silero_vad_lite', '_sounddevice_data', 'tokenizers', 'onnxruntime', 'charset_normalizer']:
    try:
        datas += collect_data_files(package)
        binaries += collect_dynamic_libs(package)
    except Exception as e:
        print(f'WARNING: could not collect files of {package}: {e}')

# Packages that look up their own (or their plugins') installed metadata at runtime
for distribution in ['anthropic', 'gradio', 'gradio_client', 'huggingface_hub', 'tokenizers', 'tqdm', 'requests', 'regex', 'packaging', 'filelock', 'numpy', 'pyyaml',
                     'opentelemetry-api', 'opentelemetry-sdk', 'opentelemetry-exporter-otlp-proto-grpc', 'opentelemetry-exporter-otlp-proto-http',
                     'opentelemetry-instrumentation', 'opentelemetry-instrumentation-requests', 'opentelemetry-instrumentation-logging']:
    try:
        datas += copy_metadata(distribution)
    except Exception as e:
        print(f'WARNING: could not copy metadata of {distribution}: {e}')

for package in ['src', 'opentelemetry', 'moonshine_onnx', 'sounddevice', 'anthropic']:
    hiddenimports += collect_submodules(package)

a = Analysis(
    [os.path.join(project_root, 'main.py')],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'matplotlib', 'IPython'],
    noarchive=False,
    # gradio reads the source code of its own components at runtime, so it has to be bundled as .py files
    module_collection_mode={'gradio': 'py'},
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Mantella',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=os.path.join(project_root, 'Mantella.ico'),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='Mantella',
)
