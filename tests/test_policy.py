import pytest
from src.policy import PolicyEngine


def test_allows_clean_text():
    engine = PolicyEngine(denylist=["confidential"])
    decision = engine.check("What is the weather today?")
    assert decision.allowed is True
    assert decision.reason is None


def test_blocks_denylisted_term_case_insensitive():
    engine = PolicyEngine(denylist=["confidential"])
    decision = engine.check("Please summarize this CONFIDENTIAL memo")
    assert decision.allowed is False
    assert "confidential" in decision.reason


def test_custom_rule_can_block():
    def no_shouting(text):
        return "text is all caps" if text.isupper() else None

    engine = PolicyEngine(custom_rules=[no_shouting])
    decision = engine.check("WHY IS EVERYONE YELLING")
    assert decision.allowed is False
    assert decision.reason == "text is all caps"


def test_custom_rule_allows_when_none_returned():
    engine = PolicyEngine(custom_rules=[lambda text: None])
    assert engine.check("anything").allowed is True


def test_denylist_does_not_false_positive_on_substring():
    engine = PolicyEngine(denylist=["ssn"])
    # "assassin" contains the substring "ssn" but is not the word "ssn"
    decision = engine.check("The word assassin contains those letters.")
    assert decision.allowed is True


def test_denylist_matches_whole_word_case_insensitively():
    engine = PolicyEngine(denylist=["ssn"])
    decision = engine.check("Can you tell me my SSN?")
    assert decision.allowed is False
    assert "ssn" in decision.reason


def test_denylist_matches_multi_word_phrase():
    engine = PolicyEngine(denylist=["wire transfer"])
    decision = engine.check("Please process a wire transfer today.")
    assert decision.allowed is False
    assert "wire transfer" in decision.reason


def test_from_config_loads_denylist(tmp_path):
    config_path = tmp_path / "policy.json"
    config_path.write_text('{"version": "1.0", "denylist": ["wire transfer", "close my account"]}')

    engine = PolicyEngine.from_config(config_path)

    assert engine.check("please process a wire transfer").allowed is False
    assert engine.check("what's my balance?").allowed is True


def test_from_config_missing_file_raises_clear_error(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError, match="policy config not found"):
        PolicyEngine.from_config(missing)


def test_from_config_malformed_json_raises_clear_error(tmp_path):
    config_path = tmp_path / "bad.json"
    config_path.write_text("{not valid json")
    with pytest.raises(ValueError, match="not valid JSON"):
        PolicyEngine.from_config(config_path)


def test_from_config_accepts_custom_rules_alongside_file_denylist(tmp_path):
    config_path = tmp_path / "policy.json"
    config_path.write_text('{"denylist": ["wire transfer"]}')

    def no_shouting(text):
        return "text is all caps" if text.isupper() else None

    engine = PolicyEngine.from_config(config_path, custom_rules=[no_shouting])

    assert engine.check("wire transfer please").allowed is False
    assert engine.check("PLEASE HELP ME NOW").allowed is False
    assert engine.check("a normal request").allowed is True
