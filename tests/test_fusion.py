from assistant.search import reciprocal_rank_fusion


def test_a_document_found_by_both_legs_outranks_one_found_by_either_alone():
    dense = ["a", "b", "c"]
    lexical = ["c", "d", "a"]
    assert reciprocal_rank_fusion([dense, lexical])[0] == "a"


def test_a_document_found_only_once_still_appears():
    fused = reciprocal_rank_fusion([["a", "b"], ["c"]])
    assert set(fused) == {"a", "b", "c"}


def test_the_top_of_a_single_list_survives_fusion_with_an_empty_one():
    assert reciprocal_rank_fusion([["a", "b"], []]) == ["a", "b"]


def test_ties_are_broken_deterministically():
    first = reciprocal_rank_fusion([["a", "b"], ["a", "b"]])
    second = reciprocal_rank_fusion([["a", "b"], ["a", "b"]])
    assert first == second
