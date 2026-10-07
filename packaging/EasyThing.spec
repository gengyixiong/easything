from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

root = Path(SPECPATH).parent
analysis = Analysis(
    [str(root / "launch.py")], pathex=[str(root)],
    binaries=collect_dynamic_libs("litert_lm") + collect_dynamic_libs("pymupdf"),
    datas=collect_data_files("pptx") + copy_metadata("lancedb") + copy_metadata("litert-lm-api"),
    hiddenimports=collect_submodules("win32com.client") + ["pythoncom", "pywintypes"],
    excludes=["pytest", "IPython", "matplotlib", "pandas", "scipy", "torch", "tensorflow", "numba",
              "huggingface_hub", "hf_xet", "openai", "sentence_transformers", "transformers"],
)
archive = PYZ(analysis.pure)
exe = EXE(archive, analysis.scripts, [], exclude_binaries=True, name="EasyThing", console=False, upx=False)
distribution = COLLECT(exe, analysis.binaries, analysis.datas, name="EasyThing", upx=False)
