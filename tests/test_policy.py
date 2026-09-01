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
