from triplens.rewrite import check_sentence

SRC = ("City Council request the General Manager, Transportation Services, to report to the Infrastructure and "
       "Environment Committee in the first quarter of 2027. The cost is $0.6M for 4,177 annual hours.")


def test_accepts_faithful_sentence():
    assert check_sentence("Council asks the General Manager to report in the first quarter of 2027.",
                          "to report to the Infrastructure and Environment Committee in the first quarter of 2027", SRC) is None


def test_rejects_quote_not_in_source():
    assert "quote not found" in check_sentence("Council approved it.", "City Council approved the plan", SRC)


def test_rejects_invented_number():
    r = check_sentence("The cost is $0.7M.", "The cost is $0.6M for 4,177 annual hours", SRC)
    assert r and "number not in source" in r


def test_accepts_number_with_commas_and_decimals():
    assert check_sentence("It needs 4,177 hours a year and costs $0.6M.",
                          "The cost is $0.6M for 4,177 annual hours", SRC) is None


def test_rejects_request_turned_into_must():
    r = check_sentence("The General Manager must report in 2027.",
                       "request the General Manager, Transportation Services, to report", SRC)
    assert r and "stronger wording" in r and "must" in r


def test_rejects_added_only():
    r = check_sentence("Council can receive the report for information only.",
                       "receive this report for information", "receive this report for information.")
    assert r and "only" in r


def test_strong_word_allowed_when_quote_has_it():
    assert check_sentence("The Board will consider it on November 16.",
                          "This item will be considered by Toronto Preservation Board on November 16",
                          "This item will be considered by Toronto Preservation Board on November 16, 2026.") is None


def test_curly_quotes_and_dashes_match():
    assert check_sentence("It adds 'No Stopping' areas.", "expanding ‘No Stopping’ coverage",
                          "expanding 'No Stopping' coverage of the AM and PM peak periods") is None
