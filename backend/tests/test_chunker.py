import pytest
from app.ingestion.chunker import chunk_text, TextChunk


class TestChunkTextBasic:
    def test_short_text_returns_empty(self):
        chunks = chunk_text("Hi", max_chunk_chars=800, min_chunk_chars=100, overlap_chars=50)
        assert chunks == []

    def test_single_paragraph_fits(self):
        text = "A" * 150
        chunks = chunk_text(text, max_chunk_chars=800, min_chunk_chars=100, overlap_chars=50)
        assert len(chunks) == 1
        assert isinstance(chunks[0], TextChunk)
        assert chunks[0].text == text

    def test_long_text_split_into_multiple_chunks(self):
        text = "Sentence one. " * 50
        chunks = chunk_text(text, max_chunk_chars=100, min_chunk_chars=10, overlap_chars=0)
        assert len(chunks) > 1

    def test_chunks_preserve_total_content(self):
        words = ["hello", "world", "this", "is", "a", "test"]
        text = " ".join(words)
        chunks = chunk_text(text, max_chunk_chars=200, min_chunk_chars=3, overlap_chars=0)
        reconstructed = " ".join(c.text for c in chunks)
        for w in words:
            assert w in reconstructed


class TestChunkMetadata:
    def test_chunk_has_chunk_index(self):
        text = "Sentence one. " * 30
        chunks = chunk_text(text, max_chunk_chars=50, min_chunk_chars=5, overlap_chars=3)
        assert len(chunks) >= 1
        assert chunks[0].chunk_index == 0
        if len(chunks) > 1:
            assert chunks[1].chunk_index == 1

    def test_chunk_has_content_hash(self):
        text = "A" * 200
        chunks = chunk_text(text, max_chunk_chars=800, min_chunk_chars=100, overlap_chars=50)
        assert chunks[0].content_hash != ""
        assert chunks[0].char_count == 200


class TestEdgeCases:
    def test_empty_text_returns_empty_list(self):
        chunks = chunk_text("", max_chunk_chars=100, min_chunk_chars=1, overlap_chars=0)
        assert chunks == []

    def test_whitespace_only_returns_empty(self):
        chunks = chunk_text("   \n\n  ", max_chunk_chars=100, min_chunk_chars=1, overlap_chars=0)
        assert chunks == []
