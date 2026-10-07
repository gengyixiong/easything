# V1 verification — 2026-10-07

Tested on Windows 11 x64. These are functional smoke checks, not a retrieval
benchmark. The real official 440M model was used; no mock vectors or cloud AI.

| Check | Result / evidence |
| --- | --- |
| Desktop startup and selected-folder settings | Source and frozen executable checks passed; Qt window render inspected |
| Unselected folders and disabled folders | Excluded from traversal and search |
| Include subfolders off | Nested files excluded |
| PPTX | Two independent slide units; real PowerPoint rendering tested |
| PowerPoint unavailable | Forced COM unavailability produced text-only slide units without a crash |
| PDF | Independent page text + rendered image embeddings |
| JPG/JPEG/PNG/WEBP/HEIC | All decoded and indexed using real vision inference |
| TXT/MD | Indexed and naturally retrieved |
| Natural-language and exact code search | Revit project proposal, visual red shape, IFC4 and 0x80070005 checks passed |
| Windows native FTS + hybrid | ICU tokenization and built-in fusion passed; new rows searchable after FTS creation |
| File events | Real watchdog create, modify, move and delete passed |
| Incremental content | Changing one PDF page made exactly one new real embedding |
| Restart | Index persisted; unchanged files were not queued for re-embedding |
| Preserved size/mtime notification | Forced hash check detected changed content |
| CPU fallback | Synthetic GPU initialization failure retried actual CPU inference successfully |
| AMD GPU | Real text and interleaved image/text inference succeeded on RX 6800 XT through WebGPU / Direct3D 12 |
| Broken image | Reported and skipped while the worker continued |
| Original documents | Fixture file hashes unchanged by indexing |
| Official model download | Fresh HTTPS download, progress, pinned SHA-256 verification passed |
| Frozen executable | Same real-model smoke checks passed with bundled Python and DLLs |
| Installer | Real unattended per-user installation succeeded |
| Default uninstall | Model, index, settings and cache preserved |
| Selected uninstall cleanup | Model, index, settings and cache removed; original document outside app data survived unchanged |

`tests/smoke.py` runs the main source check. The packaged executable runs the
same check using `--smoke <absolute-report-path>`. `tests/installer-smoke.ps1`
tests installation and both uninstall policies, and refuses to overwrite existing
user settings. It removes EasyThing test data only, so run it before personal use.

Interactive uninstall checkboxes are unchecked by default and the Inno script
compiled successfully; cleanup was exercised using the corresponding unattended
flags. The native uninstall dialog was not automatically clicked. NVIDIA and
Intel hardware were not physically tested. The installer is currently unsigned.

## Final artifact

`EasyThing-Setup.exe`: 222,952,313 bytes.

SHA-256:
`598b30159d9c581f62ae2fe62b718de0d3f5189b71a54cc857ca8a9f5e4f5bb1`

The model is not in the installer. Its download remains in the user's EasyThing
data folder and is reused on upgrades unless explicitly removed during uninstall.
