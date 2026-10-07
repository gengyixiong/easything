# Third-party software

EasyThing is GPL-3.0-or-later, based on File Brain by Hamza Abbad (Hamza5).
See LICENSE and NOTICE. Source: https://github.com/gengyixiong/easything

The standalone distribution includes dependency license and copyright files
under licenses/. Its shared libraries remain separate and replaceable.

- Python: PSF license — https://www.python.org/
- PySide6 / Qt / Shiboken: LGPLv3/GPLv3 — https://code.qt.io/pyside/pyside-setup/
- LiteRT-LM: Apache-2.0 — https://github.com/google-ai-edge/LiteRT-LM
- LanceDB / Lance: Apache-2.0 — https://github.com/lancedb/lancedb
- PyArrow: Apache-2.0 — https://github.com/apache/arrow
- PyMuPDF / MuPDF: AGPLv3 — https://github.com/pymupdf/PyMuPDF
- python-pptx: MIT — https://github.com/scanny/python-pptx
- Pillow: HPND — https://github.com/python-pillow/Pillow
- pillow-heif: BSD-3-Clause; libheif: LGPL — https://github.com/bigcat88/pillow_heif
- watchdog: Apache-2.0 — https://github.com/gorakhargosh/watchdog
- pywin32: PSF-style — https://github.com/mhammond/pywin32

EmbeddingGemma 2 weights are downloaded separately. Google's current model card
and official LiteRT distribution list Apache-2.0:
https://huggingface.co/google/embeddinggemma-2
https://huggingface.co/litert-community/embeddinggemma-2-text-vision-440m-litert-lm

Combining GPLv3 EasyThing with AGPLv3 PyMuPDF applies AGPLv3 requirements to that
combination under GPLv3 section 13; the EasyThing source remains GPLv3-or-later.
The installer ships the corresponding notices. Contact the project through its
GitHub issues for corresponding dependency source/build details if needed.
