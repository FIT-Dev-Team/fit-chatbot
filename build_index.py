# build_index.py  (CSV only, cosine, batch-encode)
import os, csv, re
from pathlib import Path
from typing import List, Dict, Tuple

import chromadb
from sentence_transformers import SentenceTransformer

# ---- paths / constants ----
DATA_DIR    = Path("data")
CSV_PATH    = DATA_DIR / "faq.csv"                 # ต้องมีคอลัมน์: Question, Answer
INDEX_PATH  = os.getenv("INDEX_PATH", "index")
COLL_NAME   = os.getenv("COLL_NAME", "fit_faq")

EMB_MODEL      = os.getenv("EMB_MODEL", "all-MiniLM-L6-v2")
EMBED_BATCH    = int(os.getenv("EMBED_BATCH", 64))         # ลดเป็น 32 ถ้า RAM น้อย
NORMALIZE_EMB  = os.getenv("NORMALIZE_EMB", "1") == "1"    # ใช้ normalization

# ---- init ----
client   = chromadb.PersistentClient(path=INDEX_PATH)
embedder = SentenceTransformer(EMB_MODEL)

def clean_text(s: str) -> str:
    s = s.replace("\u00ad", "")                 # soft hyphen
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{2,}", "\n\n", s)
    return s.strip()

def load_csv_faq(path: Path) -> List[Tuple[str, Dict]]:
    """
    คืนค่า list ของ (document_text, meta)
    document_text = Question + 2 newlines + Answer   <-- ช่วยให้ retrieval แม่นขึ้น
    meta['question'] เก็บไว้ใช้อ้างอิง [Q#] ตอนตอบ
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    rows: List[Tuple[str, Dict]] = []
    with path.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        if not {"Question", "Answer"}.issubset(rdr.fieldnames or []):
            raise ValueError("CSV must contain 'Question' and 'Answer' columns.")

        for r in rdr:
            q = clean_text((r.get("Question") or "").strip())
            a = clean_text((r.get("Answer") or "").strip())
            if not q or not a:
                continue
            doc = f"{q}\n\n{a}"                                  # << รวม Q + A
            rows.append((doc, {"source": path.name, "question": q, "type": "faq"}))
    return rows

def main():
    print(f"🧹 Recreating collection at '{INDEX_PATH}' …")
    try:
        client.delete_collection(name=COLL_NAME)
    except Exception:
        pass

    # บังคับ cosine เสมอ (ให้เข้าคู่กับ retrieval.py)
    coll = client.get_or_create_collection(
        name=COLL_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    items = load_csv_faq(CSV_PATH)
    if not items:
        print("⚠️ No rows found in CSV.")
        return

    docs  = [t for t, _ in items]
    metas = [m for _, m in items]
    ids   = [f"csv-{i+1}" for i in range(len(items))]

    print(f"📄 CSV rows: {len(items)}")
    print(f"🧠 Embedding with {EMB_MODEL} (batch={EMBED_BATCH}) …")

    # ---- batch embeddings ----
    embs: List[List[float]] = []
    for i in range(0, len(docs), EMBED_BATCH):
        batch = docs[i:i+EMBED_BATCH]
        vecs = embedder.encode(
            batch,
            normalize_embeddings=NORMALIZE_EMB,
            show_progress_bar=False,
        )
        # SentenceTransformer คืนเป็น np.array → แปลงเป็น list
        embs.extend(vecs.tolist())

    # ---- upsert ----
    coll.add(documents=docs, metadatas=metas, ids=ids, embeddings=embs)

    # ตรวจนับรายการจริง
    try:
        n = coll.count()
        print(f"✅ Index built at ./{INDEX_PATH} with {n} items")
    except Exception:
        print(f"✅ Index built at ./{INDEX_PATH} with {len(docs)} items")

if __name__ == "__main__":
    main()