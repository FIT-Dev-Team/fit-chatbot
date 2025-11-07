# retrieval.py  (cosine, robust)
from __future__ import annotations
import os
from typing import List, Dict, Any

import chromadb
from sentence_transformers import SentenceTransformer

INDEX_PATH  = os.getenv("INDEX_PATH", "index")
COLL_NAME   = os.getenv("COLL_NAME", "fit_faq")
EMB_MODEL   = os.getenv("EMB_MODEL") or os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
NORMALIZE   = os.getenv("NORMALIZE_EMB", "1") == "1"

_client   = chromadb.PersistentClient(path=INDEX_PATH)
# ใช้ cosine ให้ตรงกับตอน build
_coll     = _client.get_or_create_collection(name=COLL_NAME, metadata={"hnsw:space": "cosine"})
_embedder = SentenceTransformer(EMB_MODEL)

def _count() -> int:
    try:
        return _coll.count()
    except Exception:
        return -1

def retrieve(query: str, k: int = 5, min_sim: float = 0.20) -> List[Dict[str, Any]]:
    """
    คืนค่า: [{'text': str, 'meta': dict, 'score': float}, ...]  โดย score ~ similarity(0..1)
    - ใช้ embedding จาก SentenceTransformer (เหมือนตอน build)
    - query ผ่าน cosine distance -> แปลงเป็น similarity ด้วย 1 - dist
    """
    q = (query or "").strip()
    if not q or _count() <= 0:
        return []

    qv = _embedder.encode([q], normalize_embeddings=NORMALIZE).tolist()

    res = _coll.query(
        query_embeddings=qv,
        n_results=max(1, k),
        include=["documents", "metadatas", "distances"],   # ไม่ต้อง include 'ids'
    )
    if not res or not res.get("documents"):
        return []

    docs  = res["documents"][0] or []
    metas = res["metadatas"][0] or []
    dists = res["distances"][0] or []

    out: List[Dict[str, Any]] = []
    for doc, meta, dist in zip(docs, metas, dists):
        sim = 1.0 - float(dist)   # cosine distance -> similarity
        if sim >= min_sim:
            out.append({"text": doc, "meta": meta or {}, "score": sim})

    out.sort(key=lambda x: x["score"], reverse=True)
    return out