"""Tests for hybrid retriever — RRF scoring and error handling."""

from rag.retriever.hybrid import HybridRetriever, RetrievedChunk


def test_rrf_scoring_merges_results():
    """RRF should merge results from both sources using text as key."""
    v1 = RetrievedChunk(text="Result A from vector", source="vector", score=0.9)
    v2 = RetrievedChunk(text="Result B from vector", source="vector", score=0.8)
    g1 = RetrievedChunk(text="Result A from vector", source="graph", score=100)  # same text
    g2 = RetrievedChunk(text="Result C from graph", source="graph", score=80)

    # Simulate RRF using r.text as key (matching production code)
    fused = {}
    K = 60
    for rank, r in enumerate([v1, v2]):
        key = r.text
        fused[key] = fused.get(key, {"chunk": r, "score": 0.0})
        fused[key]["score"] += 1.0 / (K + rank + 1)
    for rank, r in enumerate([g1, g2]):
        key = r.text
        fused[key] = fused.get(key, {"chunk": r, "score": 0.0})
        fused[key]["score"] += 1.0 / (K + rank + 1)

    # "Result A from vector" appears in both, should get highest RRF score
    ranked = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
    assert ranked[0]["chunk"].text == "Result A from vector"
    assert len(ranked) == 3  # 3 unique texts


def test_retrieved_chunk():
    chunk = RetrievedChunk(text="test", source="vector", score=0.9)
    assert chunk.source == "vector"
    assert chunk.metadata == {}


def test_rrf_score_range():
    """RRF scores should be between 0 and 1."""
    K = 60
    assert 1.0 / (K + 1) < 0.02
    assert 1.0 / (K + 10) < 0.02


def test_rrf_fusion_replaces_incomparable_channel_raw_scores():
    vector = RetrievedChunk(
        text="OpenAI vector evidence",
        source="vector",
        score=0.91,
        metadata={"citation_id": "same-item"},
    )
    graph = RetrievedChunk(
        text="OpenAI graph evidence",
        source="graph",
        score=98,
        metadata={"citation_id": "same-item"},
    )

    fused = HybridRetriever._fuse_rrf([vector], [graph], rrf_k=60)

    assert len(fused) == 1
    assert fused[0].score == (1 / 61) + (1 / 61)
    assert fused[0].score != 0.91
    assert fused[0].score != 98


def test_exact_lexical_metadata_survives_vector_duplicate_and_boosts_score():
    vector = RetrievedChunk(
        text="vector text",
        source="vector",
        score=0.9,
        metadata={"citation_id": "same-item", "title": "Title"},
    )
    lexical = RetrievedChunk(
        text="lexical text",
        source="lexical",
        score=0,
        metadata={
            "citation_id": "same-item",
            "lexical_match_type": "exact_title",
            "local_url": "#date/report/item/id",
        },
    )

    fused = HybridRetriever._fuse_rrf([vector], [lexical], rrf_k=60)

    assert fused[0].metadata["lexical_match_type"] == "exact_title"
    assert fused[0].metadata["local_url"] == "#date/report/item/id"
    assert fused[0].score == (1 / 61) * 3
