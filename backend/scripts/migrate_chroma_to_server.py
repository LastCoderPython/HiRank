"""
ChromaDB Migration: Embedded (PersistentClient) → Server (HttpClient)

One-time script to copy all collections and their data from the old
embedded ChromaDB on disk to the new standalone ChromaDB server.

Usage:
    # 1. Start the new ChromaDB server first:
    #    docker-compose up chromadb -d
    #
    # 2. Run the migration from the backend directory:
    #    python -m scripts.migrate_chroma_to_server
    #
    # 3. Verify counts match, then delete ./data/chroma if desired.
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("chroma-migration")

# ── Configuration ─────────────────────────────────────────────────────
OLD_PERSIST_DIR = os.environ.get("OLD_CHROMA_DIR", "./data/chroma")
NEW_HOST = os.environ.get("CHROMA_HOST", "localhost")
NEW_PORT = int(os.environ.get("CHROMA_PORT", "8000"))
AUTH_TOKEN = os.environ.get("CHROMA_AUTH_TOKEN", "")

COLLECTIONS_TO_MIGRATE = ["cee", "jee", "college_web_docs"]
BATCH_SIZE = 100  # ChromaDB recommends batches of 100 for upserts


def main():
    # ── Connect to OLD embedded database ──────────────────────────────
    if not os.path.exists(OLD_PERSIST_DIR):
        logger.error("Old ChromaDB directory not found: %s", OLD_PERSIST_DIR)
        logger.error("Nothing to migrate. Exiting.")
        sys.exit(1)

    logger.info("Connecting to OLD embedded ChromaDB at: %s", OLD_PERSIST_DIR)
    old_client = chromadb.PersistentClient(
        path=OLD_PERSIST_DIR,
        settings=ChromaSettings(anonymized_telemetry=False),
    )

    # ── Connect to NEW server ─────────────────────────────────────────
    logger.info("Connecting to NEW ChromaDB server at: %s:%s", NEW_HOST, NEW_PORT)
    new_kwargs = {
        "host": NEW_HOST,
        "port": NEW_PORT,
        "settings": ChromaSettings(anonymized_telemetry=False),
    }
    if AUTH_TOKEN:
        new_kwargs["headers"] = {"Authorization": f"Bearer {AUTH_TOKEN}"}

    new_client = chromadb.HttpClient(**new_kwargs)

    # Verify connectivity
    try:
        new_client.heartbeat()
        logger.info("✅ Connected to ChromaDB server successfully.")
    except Exception as e:
        logger.error("❌ Cannot connect to ChromaDB server: %s", e)
        sys.exit(1)

    # ── Migrate each collection ───────────────────────────────────────
    for col_name in COLLECTIONS_TO_MIGRATE:
        try:
            old_col = old_client.get_collection(col_name)
        except Exception:
            logger.warning("Collection '%s' not found in old database. Skipping.", col_name)
            continue

        old_count = old_col.count()
        logger.info("Migrating collection '%s' (%d documents)...", col_name, old_count)

        if old_count == 0:
            logger.info("  Empty collection, skipping.")
            continue

        # Create the collection on the new server
        new_col = new_client.get_or_create_collection(
            name=col_name,
            metadata={"hnsw:space": "cosine"},
        )

        # Read all data from the old collection
        all_data = old_col.get(
            include=["documents", "embeddings", "metadatas"],
        )

        ids = all_data["ids"]
        documents = all_data["documents"]
        embeddings = all_data["embeddings"]
        metadatas = all_data["metadatas"]

        # Upsert in batches
        total_batches = (len(ids) + BATCH_SIZE - 1) // BATCH_SIZE
        for batch_idx in range(total_batches):
            start = batch_idx * BATCH_SIZE
            end = min(start + BATCH_SIZE, len(ids))

            batch_kwargs = {
                "ids": ids[start:end],
            }
            if documents:
                batch_kwargs["documents"] = documents[start:end]
            if embeddings:
                batch_kwargs["embeddings"] = embeddings[start:end]
            if metadatas:
                batch_kwargs["metadatas"] = metadatas[start:end]

            new_col.upsert(**batch_kwargs)
            logger.info(
                "  Batch %d/%d (%d docs)", batch_idx + 1, total_batches, end - start
            )

        # Verify count matches
        new_count = new_col.count()
        if new_count == old_count:
            logger.info("  ✅ '%s': %d → %d documents (verified)", col_name, old_count, new_count)
        else:
            logger.warning(
                "  ⚠️ '%s': count mismatch! Old=%d, New=%d", col_name, old_count, new_count
            )

    logger.info("")
    logger.info("═══════════════════════════════════════════════════════")
    logger.info("  Migration complete!")
    logger.info("  You may now safely delete: %s", OLD_PERSIST_DIR)
    logger.info("═══════════════════════════════════════════════════════")


if __name__ == "__main__":
    main()
