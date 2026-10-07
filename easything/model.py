"""One official Text + Vision model; no network calls during inference."""

import hashlib
import logging
import math
import urllib.request
from pathlib import Path

from litert_lm import Backend, Content, EmbeddingEngine, EmbeddingOptions

MODEL_FILE = "embeddinggemma-2-text-vision-440m.litertlm"
MODEL_REVISION = "e301f74d5551b0c2641bd5cb4652a76239d5c5f8"
MODEL_REPO = "litert-community/embeddinggemma-2-text-vision-440m-litert-lm"
MODEL_SHA256 = "92dcbea108899e5d6e30d919b0744f90d9967e80c67a4ab5503ac16d54f62eb0"
MODEL_SIZE = 387710976
MODEL_URL = f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{MODEL_FILE}"


def verify_model(path):
    if not path.is_file() or path.stat().st_size != MODEL_SIZE:
        return False
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() == MODEL_SHA256


def download_model(directory, progress):
    """Stream to a temporary file, verify the pinned digest, then publish."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / MODEL_FILE
    if verify_model(target):
        progress(MODEL_SIZE, MODEL_SIZE)
        return target
    partial = target.with_suffix(".download")
    request = urllib.request.Request(MODEL_URL, headers={"User-Agent": "EasyThing/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as stream:
            count = 0
            while block := response.read(1024 * 1024):
                stream.write(block)
                count += len(block)
                progress(count, MODEL_SIZE)
        if not verify_model(partial):
            raise ValueError("The model download is incomplete. Please retry.")
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return target


class Embedder:
    def __init__(self, root, cpu_only=False):
        self.root = Path(root)
        self.path = self.root / "models" / MODEL_FILE
        self.engine = None
        self.backend = "CPU" if cpu_only else "Auto"
        self.cpu_only = cpu_only

    def close(self):
        if self.engine is not None:
            self.engine.close()
            self.engine = None

    def _load(self, gpu):
        if not verify_model(self.path):
            raise ValueError("Download EmbeddingGemma 2 before indexing or searching.")
        backend = Backend.GPU() if gpu else Backend.CPU()
        self.engine = EmbeddingEngine(
            str(self.path), backend=backend, vision_backend=backend,
            cache_dir=str(self.root / "cache"), max_input_length=8192,
        )
        self.backend = "GPU" if gpu else "CPU"

    def encode(self, text="", image=None, query=False):
        # LiteRT-LM task prefixes, per Google's embedding_models documentation.
        contents = []
        if text.strip() or query:
            task = "search query" if query else "search result"
            contents.append(f"task: {task} | text: {text.strip()}")
        if image is not None:
            contents.append(Content.ImageBytes(image))
        if not contents:
            contents = ["task: search result | text: "]
        options = EmbeddingOptions(normalize=True, output_size=768)
        try:
            if self.engine is None:
                self._load(not self.cpu_only)
            vector = self.engine.compute_embedding(contents, options).embedding
            if len(vector) != 768 or not all(math.isfinite(value) for value in vector):
                raise ValueError("The embedding runtime returned an invalid vector.")
        except Exception:
            if self.cpu_only or self.backend == "CPU":
                raise
            logging.exception("GPU unavailable; retrying on CPU")
            self.close()
            self.cpu_only = True
            self._load(False)
            vector = self.engine.compute_embedding(contents, options).embedding
            if len(vector) != 768 or not all(math.isfinite(value) for value in vector):
                raise ValueError("The CPU embedding runtime returned an invalid vector.")
        return vector
