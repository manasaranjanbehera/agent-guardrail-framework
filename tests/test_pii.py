from src.pii import contains_pii, redact


def test_redacts_email():
    assert redact("contact me at jane.doe@example.com please") == \
        "contact me at [REDACTED:EMAIL] please"


def test_redacts_ssn():
    assert redact("my ssn is 123-45-6789 on file") == "my ssn is [REDACTED:SSN] on file"


def test_redacts_credit_card():
    result = redact("card number 4111 1111 1111 1111 expires soon")
    assert "[REDACTED:CREDIT_CARD]" in result
    assert "4111" not in result


def test_redacts_phone():
    result = redact("call me at 415-555-1234 tomorrow")
    assert "[REDACTED:PHONE]" in result
    assert "555-1234" not in result


def test_leaves_non_pii_text_untouched():
    text = "The quarterly report is due Friday."
    assert redact(text) == text


def test_contains_pii_true_and_false():
    assert contains_pii("email me at a@b.com") is True
    assert contains_pii("no personal data in this sentence") is False
