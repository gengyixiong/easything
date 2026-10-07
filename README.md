# EasyThing

AI-powered local file search for Windows.

EasyThing searches local file content and images using natural language. Its
minimal desktop interface has one search box and automatic hybrid retrieval.
Your documents and photos stay on your computer; no cloud AI API is used.

## Features

- EmbeddingGemma 2 Text + Vision, 440M parameters, native **768d** embeddings.
- PPTX slide search and PDF page search; one main embedding per slide/page.
- Photo semantic search: JPG, JPEG, PNG, WEBP and HEIC.
- TXT and Markdown search, with simple length-based splitting for long text.
- Local LanceDB vector + full-text hybrid search using its built-in RRF fusion.
- Only folders you explicitly add are scanned; never a whole-computer first scan.
- Automatic create/modify/delete/move updates and lightweight startup reconciliation.
- Unchanged page/slide content hashes reuse existing embeddings.
- Automatic GPU acceleration through Google's LiteRT-LM; CPU fallback.
- A Windows installer with Python and dependencies included.

## Install and use

Download **EasyThing-Setup.exe** from [Releases](https://github.com/gengyixiong/easything/releases).
Install it, then open EasyThing from the Start Menu.

1. Click **Add Folder** and select the directories you want to search.
2. Click **Download / Retry model** once. Downloading requires internet; indexing
   and searching do not. Downloads are verified before use.
3. Wait for initial indexing. Pause and resume are available.
4. Type a natural-language query. Results update after a 300ms typing pause.
5. Double-click a result to open the original file. The context menu provides
   Open, Open file location and Copy path.

Examples:

- 找那个讲 Revit interoperability 和 MEP 的 PPT
- 找有彩色建筑点云那一页的 PPT
- 找那个介绍 IFC certification 的 PDF
- 找猫趴在饮水机旁边的照片
- 找写过某个项目方案的 markdown

Settings lets you enable/disable folders, change whether subfolders are included,
remove folders from the index, rebuild the local index and enable Windows startup.
Disabled folders retain their index but are not scanned or searched. Removing a
folder removes its EasyThing index entries; it never removes the source files.
Closing the window keeps EasyThing in the tray. Use tray → Exit to stop it.

## Local data and privacy

All application data is under `%LOCALAPPDATA%\EasyThing\`:

- `models\`: downloaded model, reused across application upgrades
- `index\`: embedded LanceDB and a small SQLite file manifest
- `cache\`: temporary rendering/runtime data and index-rebuild recovery backups
- `settings\`: selected folders and application settings
- `logs\`: small rotating diagnostic logs

Original documents are opened read-only. The only application download request
fetches the official model; file contents, images and search queries are never
sent to a network endpoint. There is no telemetry, local HTTP server, Docker,
Typesense, Tika, chat/RAG feature or cloud AI provider.

## Model and hardware

The runtime is Google's [LiteRT-LM Python API](https://developers.google.com/edge/litert-lm/python).
The model is the official [Text + Vision 440M LiteRT variant](https://huggingface.co/litert-community/embeddinggemma-2-text-vision-440m-litert-lm)
of [EmbeddingGemma 2](https://huggingface.co/google/embeddinggemma-2).
It excludes the audio encoder. The normal installer does not contain the weights.
The official model card and distribution list **Apache-2.0**; consult those sources
for the current model license and usage guidance.

The pinned download is 387,710,976 bytes, revision
`e301f74d5551b0c2641bd5cb4652a76239d5c5f8`, SHA-256
`92dcbea108899e5d6e30d919b0744f90d9967e80c67a4ab5503ac16d54f62eb0`.
An incomplete or invalid download is discarded and can be retried.

Text uses the task prefixes documented for the LiteRT runtime. Native ordered
text/image content inputs produce a single multimodal embedding. The app does
not load separate text/image vector sets, captions, OCR or a second AI model.

Auto tries the SDK GPU backend and retries on CPU after GPU initialization or
inference errors. No CUDA, ROCm or GPU-specific installer is needed. GPU support
still depends on hardware and drivers; CPU is always available. Developers can
force CPU using `--cpu`. AMD Radeon RX 6800 XT GPU and CPU were tested locally;
NVIDIA and Intel hardware have not been tested by this project.

## V1 limitations

- Windows x64 only. No audio, video, DOCX, XLSX, archives or cloud drives.
- PDF pages render locally through PyMuPDF. Password-protected PDFs are skipped.
- PPTX visible shape/table/group text is read with python-pptx. Slide images use
  installed Microsoft PowerPoint through COM. Missing/unavailable PowerPoint,
  or a presentation already open in PowerPoint, falls back to text-only indexing.
  There is no bundled alternative PowerPoint renderer.
- Double-click opens the original file; automatic navigation to a slide/page and
  thumbnails are not implemented in V1.
- TXT/MD accept UTF-8 and BOM-marked UTF-16. Unsupported encodings are reported.
- Vector retrieval uses exact search for now. Large corpora may need a LanceDB
  ANN index after real latency warrants it. The UI shows up to 100 unique files
  from 300 candidate units.
- Rebuild Index preserves the old local database in cache for recovery. It does
  not delete originals. Bad files are skipped with an on-screen status and log.

## Uninstall

Exit EasyThing from the tray, then run Uninstall EasyThing from the Start Menu
or Windows Installed apps. Application removal is enabled. These cleanup options
are **unchecked by default**:

- Delete downloaded EmbeddingGemma 2 model
- Delete local search index
- Delete settings and cache

**Original documents and photos will never be deleted.** Cleanup is limited to
fixed EasyThing application-data subdirectories and never follows junctions or
symlinks. Keeping model/index/settings allows reuse after reinstalling.

## Develop and build

Prerequisites for developers: Windows x64, Python 3.12 and Inno Setup 6.6 or newer. End users need none of these.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe launch.py
```

Download the model using the app before running the real-model smoke check:

```powershell
.venv\Scripts\python.exe tests\smoke.py
.\build.ps1
```

Nuitka was evaluated; its cold build compiled nearly a thousand dependency modules.
V1 uses PyInstaller folder mode and Inno Setup only, with the same real-model smoke checks. Output:
`dist\EasyThing-Setup.exe`. Shared libraries and their notices are included;
model weights are kept out of the installer. The same smoke check can run against
the packaged executable with `EasyThing.exe --smoke <absolute-report-path>`.

## License and origin

Based on [File Brain by Hamza Abbad (Hamza5)](https://github.com/Hamza5/file-brain),
imported from commit `aca4df9fe0821148fcd87c9a9c918aa0476536dd` into a new Git history.
EasyThing source continues under **GPL-3.0-or-later**. The GPLv3 [LICENSE](LICENSE)
and necessary original author attribution in [NOTICE](NOTICE) are preserved.
The original container/web architecture has been replaced with a desktop app.

See [THIRD_PARTY.md](THIRD_PARTY.md) and the installer distribution's `licenses\`
folder for bundled dependency notices. PyMuPDF is AGPLv3; GPLv3 section 13 applies
AGPL requirements to the combined distribution while EasyThing source remains GPLv3.
