from ingestion.build_index import _chunks


def test_long_content_is_split_into_bounded_overlapping_chunks():
    words = [f"word-{index}" for index in range(1000)]
    chunks = _chunks(" ".join(words), size=420, overlap=60)
    assert len(chunks) == 3
    assert max(len(chunk.split()) for chunk in chunks) <= 420
    assert chunks[0].split()[-60:] == chunks[1].split()[:60]
