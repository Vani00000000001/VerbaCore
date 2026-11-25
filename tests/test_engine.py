from verbacore.asr.engine import detect_verified_languages


def test_detect_verified_languages_tamil_full_block():
    # Tests characters across the full Tamil block (\u0B80-\u0BFF), including 0B80-0B9F
    segs = [{"text": "\u0b85\u0bae\u0bcd\u0bae\u0bbe \u0bb5\u0ba3\u0b95\u0bcd\u0b95\u0bae\u0bcd"}]
    assert detect_verified_languages(segs, {"ta"}) == ["TAMIL"]


def test_detect_verified_languages_devanagari_and_latin():
    segs = [
        {"text": "Namast\u00e9"},  # accented Latin
        {"text": "\u0928\u092e\u0938\u094d\u0924\u0947"},  # Devanagari
    ]
    assert detect_verified_languages(segs, {"hi", "en"}) == ["ENGLISH", "HINDI"]


def test_detect_verified_languages_fallback():
    segs = [{"text": "12345 !!!"}]
    assert detect_verified_languages(segs, {"fr"}) == ["FR"]
