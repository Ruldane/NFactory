"""Knowledge base (spec §7, ADR-0007), shared by the API and the worker.

Interface:
- `extract(filename, data)` returns the text of an upload (`Extracted`), or raises
  `ExtractionError` with a stable `code` and a French `message`.
- `chunk(extracted)` cuts it into `Chunk`s that keep their line range, section,
  symbol and page.
- `ingest(session, scope, filename, data)` stores a document and its chunks, skipping
  a file already in the `Scope` and replacing an older revision of the same path.
- `index_batch(session, workspace_id, embedder)` embeds pending chunks with an
  `Embedder` (`LocalHashEmbedder`, `ProviderEmbedder`); `index_status` counts them.
- `search(session, scope, query, embedder=...)` returns `Hit`s: access control first,
  then full text + vector fused by RRF.
"""

from nfactory_core.knowledge.chunking import Chunk, chunk
from nfactory_core.knowledge.extract import SUPPORTED, Extracted, ExtractionError, extract
from nfactory_core.knowledge.indexing import IndexStatus, index_batch, index_status
from nfactory_core.knowledge.search import Hit, search
from nfactory_core.knowledge.store import Ingested, Scope, clean_path, ingest

__all__ = [
    "SUPPORTED",
    "Chunk",
    "Extracted",
    "ExtractionError",
    "Hit",
    "IndexStatus",
    "Ingested",
    "Scope",
    "chunk",
    "clean_path",
    "extract",
    "index_batch",
    "index_status",
    "ingest",
    "search",
]
