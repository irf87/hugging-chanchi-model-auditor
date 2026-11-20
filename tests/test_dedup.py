"""Duplicate detection: tokens, coverage, the two match tests and their boundaries."""

import json
from pathlib import Path

import pytest

from chanchi import dedup

FIXTURES = Path(__file__).parent / "fixtures" / "lessons"


def load_body(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def as_candidate(body, lesson_id):
    rule = body["general_rule"]
    full = f"{body['what_happened']} {rule} {body['proposal']}"
    return {"id": lesson_id, "full": full, "rule": rule}


def as_new(body):
    return as_candidate(body, None)


def word(group, i):
    """A distinct lowercase token of 4+ letters or digits, never a stopword."""
    return f"word{group}{i}"


def lesson_from_tokens(full_words, rule_words):
    """A candidate or new lesson whose token sets are exactly the given words."""
    return {"id": None, "full": " ".join(full_words), "rule": " ".join(rule_words)}


# --- tokenization -------------------------------------------------------------


def test_tokens_lowercase_split_on_punctuation_and_keep_digits():
    assert dedup.tokens("Test-output, ALPHA beta; the planner's gate. Why? run42") == {
        "test",
        "output",
        "alpha",
        "beta",
        "planner",
        "gate",
        "run42",
    }


def test_tokens_drop_words_shorter_than_four_characters():
    assert dedup.tokens("one two six ten four five") == {"four", "five"}


def test_tokens_drop_stopwords_including_domain_words():
    assert dedup.tokens("with about lesson rule session agent planner") == {"planner"}


def test_stopwords_file_loads_once_with_expected_words():
    words = dedup.load_stopwords()
    assert dedup.load_stopwords() is words
    assert {"with", "would", "through", "lesson", "agent", "session", "rule"} <= words
    assert "test" not in words


# --- coverage -----------------------------------------------------------------


def test_coverage_is_zero_when_either_set_is_empty():
    assert dedup.coverage(set(), {"alpha"}) == 0.0
    assert dedup.coverage({"alpha"}, set()) == 0.0
    assert dedup.coverage(set(), set()) == 0.0


def test_coverage_divides_by_the_smaller_set():
    assert dedup.coverage({"aaaa", "bbbb", "cccc", "dddd"}, {"aaaa", "bbbb"}) == 1.0
    assert dedup.coverage({"aaaa", "bbbb"}, {"cccc", "dddd"}) == 0.0


# --- fixtures: the CUJ 1 lesson and its neighbours ----------------------------


def test_same_rule_other_case_blocks_by_the_rule_test():
    base = as_candidate(load_body("base"), 42)
    other = as_new(load_body("same_rule_other_case"))
    found = dedup.matches(other, base)
    assert found is not None
    assert found["test"] == "rule"
    assert found["id"] == 42
    assert set(found["shared"]) == dedup.tokens(load_body("base")["general_rule"])


def test_same_case_other_words_blocks_by_the_full_text_test():
    base = as_candidate(load_body("base"), 42)
    other = as_new(load_body("same_case_other_words"))
    found = dedup.matches(other, base)
    assert found is not None
    assert found["test"] == "full"
    assert dedup.blocking_match(other, [base])["id"] == 42


def test_unrelated_lesson_passes_and_shares_exactly_two_tokens_with_base():
    base_body = load_body("base")
    unrelated_body = load_body("unrelated")
    shared = dedup.tokens(as_new(base_body)["full"]) & dedup.tokens(as_new(unrelated_body)["full"])
    assert shared == {"planner", "package"}
    assert not shared & dedup.tokens(base_body["general_rule"])
    assert dedup.matches(as_new(unrelated_body), as_candidate(base_body, 42)) is None
    assert dedup.blocking_match(as_new(unrelated_body), [as_candidate(base_body, 42)]) is None


# --- boundaries (token sets built in the test) ---------------------------------


def test_full_text_blocks_at_six_shared_of_twenty():
    shared = [word("s", i) for i in range(6)]
    new_rule = [word("r", i) for i in range(3)]
    new_full_only = [word("o", i) for i in range(11)]
    cand_rule = [word("q", i) for i in range(3)]
    cand_only = [word("p", i) for i in range(11)]
    new = lesson_from_tokens(shared + new_full_only + new_rule, new_rule)
    cand = lesson_from_tokens(shared + cand_only + cand_rule, cand_rule)
    assert len(dedup.tokens(new["full"])) == 20
    assert len(dedup.tokens(cand["full"])) == 20
    found = dedup.matches(new, {"id": 1, **cand})
    assert found is not None and found["test"] == "full"
    assert found["coverage"] == pytest.approx(0.30)


def test_full_text_does_not_block_at_four_shared_of_fourteen():
    shared = [word("s", i) for i in range(4)]
    new_rule = [word("r", i) for i in range(3)]
    new_full_only = [word("o", i) for i in range(7)]
    cand_rule = [word("q", i) for i in range(3)]
    cand_only = [word("p", i) for i in range(7)]
    new = lesson_from_tokens(shared + new_full_only + new_rule, new_rule)
    cand = lesson_from_tokens(shared + cand_only + cand_rule, cand_rule)
    assert len(dedup.tokens(new["full"])) == 14
    assert dedup.matches(new, {"id": 1, **cand}) is None


def test_full_text_does_not_block_at_three_shared_of_three():
    # Coverage is 1.0, but 3 shared tokens is under FULL_MIN_SHARED (4).
    new = lesson_from_tokens(["wordfa", "wordfb", "wordfc"], ["wordfa", "wordfb"])
    cand = lesson_from_tokens(["wordfa", "wordfb", "wordfc"], ["wordfa", "wordfb"])
    assert dedup.matches(new, {"id": 1, **cand}) is None


def test_rule_blocks_at_three_shared_of_six():
    rule = [word("r", i) for i in range(6)]
    cand_rule = rule[:3] + [word("q", i) for i in range(3)]
    new = lesson_from_tokens(rule, rule)
    cand = lesson_from_tokens(cand_rule, cand_rule)
    found = dedup.matches(new, {"id": 1, **cand})
    assert found is not None and found["test"] == "rule"
    assert found["coverage"] == pytest.approx(0.50)


def test_rule_does_not_block_at_three_shared_of_seven():
    rule = [word("r", i) for i in range(7)]
    cand_rule = rule[:3] + [word("q", i) for i in range(4)]
    new = lesson_from_tokens(rule, rule)
    cand = lesson_from_tokens(cand_rule, cand_rule)
    assert len(dedup.tokens(cand["rule"])) == 7
    assert dedup.matches(new, {"id": 1, **cand}) is None


def test_rule_does_not_block_at_two_shared_of_two():
    new = lesson_from_tokens(["wordra", "wordrb"], ["wordra", "wordrb"])
    cand = lesson_from_tokens(["wordra", "wordrb"], ["wordra", "wordrb"])
    assert dedup.matches(new, {"id": 1, **cand}) is None


# --- blocking_match and similar ------------------------------------------------


def test_blocking_match_returns_highest_coverage_then_lowest_id():
    rule = [word("r", i) for i in range(6)]
    new = lesson_from_tokens(rule, rule)

    def candidate(lesson_id, shared_count):
        # Full text = shared rule words plus four extra words, so the full test and the rule test
        # give the same coverage (shared / 6) and the full test is the one that matches.
        cand_rule = rule[:shared_count] + [word(f"x{lesson_id}", i) for i in range(6 - shared_count)]
        extra = [word(f"e{lesson_id}", i) for i in range(4)]
        return {"id": lesson_id, "full": " ".join(cand_rule + extra), "rule": " ".join(cand_rule)}

    candidates = [
        candidate(9, 4),  # coverage 0.667
        candidate(3, 4),  # coverage 0.667, tie: lowest id wins
        candidate(7, 5),  # coverage 0.833, highest
        candidate(1, 2),  # below both thresholds: no match
    ]
    best = dedup.blocking_match(new, candidates)
    assert best["id"] == 7
    assert best["coverage"] == pytest.approx(5 / 6)

    tied = dedup.blocking_match(new, [candidates[0], candidates[1]])
    assert tied["id"] == 3


def test_blocking_match_returns_none_without_a_match():
    base = as_candidate(load_body("base"), 42)
    assert dedup.blocking_match(as_new(load_body("unrelated")), [base]) is None
    assert dedup.blocking_match(as_new(load_body("unrelated")), []) is None


def test_similar_returns_at_most_five_ordered_by_coverage_shared_then_id():
    text = " ".join(word("w", i) for i in range(6))
    def candidate(lesson_id, shared_count, size):
        words = [word("w", i) for i in range(shared_count)]
        words += [word(f"x{lesson_id}", i) for i in range(size - shared_count)]
        text_of = " ".join(words)
        return {"id": lesson_id, "full": text_of, "rule": text_of}

    candidates = [
        candidate(1, 2, 6),  # 0.333, shared 2: cut by the limit
        candidate(2, 3, 6),  # 0.500, shared 3
        candidate(3, 3, 6),  # 0.500, shared 3: tie with id 2, higher id
        candidate(4, 4, 6),  # 0.667
        candidate(5, 1, 6),  # shares only 1 token: excluded
        candidate(6, 2, 4),  # 0.500, shared 2
        candidate(7, 2, 2),  # 1.000, shared 2
        candidate(8, 6, 6),  # 1.000, shared 6
    ]
    result = dedup.similar(text, candidates)
    assert [item["id"] for item in result] == [8, 7, 4, 2, 3]
    assert result[0] == {"id": 8, "coverage": 1.0, "shared": 6}
    assert result[1]["shared"] == 2
    assert len(dedup.similar(text, candidates, limit=2)) == 2
