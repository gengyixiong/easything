"""Local vectors and a tiny SQLite file manifest, owned by the worker thread."""

import hashlib
import os
import sqlite3
from pathlib import Path

import lancedb
import pyarrow as pa
from lancedb.index import FTS

from .readers import IMAGES, SUPPORTED, read_units


def canonical(path):
    return os.path.normcase(str(Path(path).resolve()))


def in_scope(path, folders, enabled_only=True):
    candidate = Path(canonical(path))
    for folder in folders:
        if enabled_only and not folder["enabled"]:
            continue
        root = Path(canonical(folder["path"]))
        if candidate.is_relative_to(root) and candidate != root:
            if folder["recursive"] or candidate.parent == root:
                return True
    return False


def selected_files(folders):
    """Never follow links or junctions into unselected folders."""
    seen = set()
    for folder in folders:
        if not folder["enabled"]:
            continue
        root = canonical(folder["path"])
        if not Path(root).is_dir():
            continue
        for directory, subdirs, names in os.walk(root, followlinks=False):
            subdirs[:] = [name for name in subdirs if not (
                Path(directory, name).is_symlink() or os.path.isjunction(Path(directory, name))
            )] if folder["recursive"] else []
            for name in names:
                path = Path(directory, name)
                if path.suffix.lower() not in SUPPORTED or name.startswith("~$"):
                    continue
                resolved = canonical(path)
                if resolved not in seen and in_scope(resolved, folders):
                    seen.add(resolved)
                    yield resolved


def sql_string(value):
    return "'" + str(value).replace("'", "''") + "'"


SCHEMA = pa.schema([
    ("id", pa.string()), ("path", pa.string()), ("name", pa.string()),
    ("number", pa.int32()), ("match", pa.string()), ("content", pa.string()),
    ("search_text", pa.string()), ("content_hash", pa.string()),
    ("file_hash", pa.string()), ("modified", pa.float64()),
    ("kind", pa.string()), ("visual", pa.bool_()),
    ("vector", pa.list_(pa.float32(), 768)),
])


class Index:
    def __init__(self, root, embedder):
        self.root = Path(root)
        self.embedder = embedder
        directory = self.root / "index"
        directory.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(directory / "vectors")
        self.table = self.db.create_table("units", schema=SCHEMA, exist_ok=True)
        self.table.count_rows()  # Detect a damaged index before work starts.
        self.manifest = sqlite3.connect(directory / "files.sqlite3")
        self.manifest.execute("CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, size INTEGER, mtime INTEGER, hash TEXT)")
        self.manifest.commit()
        self.fts_ready = False

    def close(self):
        self.manifest.close()

    def paths(self):
        return [row[0] for row in self.manifest.execute("SELECT path FROM files")]

    def remove(self, path):
        self.table.delete(f"path = {sql_string(path)}")
        self.manifest.execute("DELETE FROM files WHERE path = ?", (path,))
        self.manifest.commit()

    def index_file(self, path):
        path = canonical(path)
        source = Path(path)
        stat = source.stat()
        old = self.manifest.execute("SELECT size,mtime,hash FROM files WHERE path=?", (path,)).fetchone()
        if old and old[:2] == (stat.st_size, stat.st_mtime_ns):
            return "unchanged"
        with source.open("rb") as stream:
            file_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        previous = {row["content_hash"]: row["vector"] for row in
                    self.table.search().where(f"path = {sql_string(path)}").limit(None).to_list()}
        rows = []
        text_only = False
        for item in read_units(source, self.root / "cache"):
            vector = previous.get(item["content_hash"])
            if vector is None:
                vector = self.embedder.encode(item["content"], item["image"])
            text_only |= source.suffix.lower() == ".pptx" and item["image"] is None
            rows.append({
                "id": hashlib.sha256(f'{path}:{item["number"]}'.encode()).hexdigest(),
                "path": path, "name": source.name, "number": item["number"],
                "match": item["match"], "content": item["content"],
                "search_text": source.name + "\n" + item["content"],
                "content_hash": item["content_hash"], "file_hash": file_hash,
                "modified": stat.st_mtime,
                "kind": "Images" if source.suffix.lower() in IMAGES else "Documents",
                "visual": item["image"] is not None, "vector": vector,
            })
        after = source.stat()
        if (after.st_size, after.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
            raise OSError("The file changed while being indexed. It will be retried.")
        if rows:
            (self.table.merge_insert("id").when_matched_update_all()
             .when_not_matched_insert_all()
             .when_not_matched_by_source_delete(f"path = {sql_string(path)}")
             .execute(rows))
        else:
            self.table.delete(f"path = {sql_string(path)}")
        self.manifest.execute("INSERT OR REPLACE INTO files VALUES (?,?,?,?)",
                              (path, stat.st_size, stat.st_mtime_ns, file_hash))
        self.manifest.commit()
        return "PPTX text indexed; slide visuals unavailable (PowerPoint required)." if text_only else "indexed"

    def search(self, text, folders, kind="All"):
        if not text.strip() or not self.table.count_rows():
            return []
        if not self.fts_ready:
            self.table.create_index("search_text", config=FTS(
                base_tokenizer="icu", stem=False, remove_stop_words=False, ascii_folding=False,
            ))
            self.fts_ready = True
        roots = []
        for folder in folders:
            if not folder["enabled"]:
                continue
            root = canonical(folder["path"]).rstrip("\\/") + os.sep
            # starts_with avoids treating %, _ and apostrophes as path wildcards.
            condition = f"starts_with(path, {sql_string(root)})"
            if not folder["recursive"]:
                condition += f" AND NOT contains(substr(path, {len(root)+1}), {sql_string(os.sep)})"
            roots.append(f"({condition})")
        if not roots:
            return []
        where = "(" + " OR ".join(roots) + ")"
        if kind != "All":
            where += f" AND kind = {sql_string(kind)}"
        vector = self.embedder.encode(text, query=True)
        # ponytail: exact vector scan; add a LanceDB ANN index when real corpus latency requires it.
        rows = (self.table.search(query_type="hybrid").vector(vector).text(text)
                .where(where).distance_type("cosine").limit(300).to_list())
        results, seen = [], set()
        for row in rows:
            if row["path"] not in seen and in_scope(row["path"], folders):
                seen.add(row["path"])
                row.pop("vector", None)
                results.append(row)
        return results[:100]
