from app.services.voice_intent_service import (
    INTENT_DETAIL_EMAIL,
    INTENT_END_CALL,
    INTENT_HELP,
    INTENT_IMPORTANT_CHECK,
    INTENT_REPEAT_SUMMARY,
    INTENT_START_EMAIL_REPLY,
    INTENT_CAPTURE_REPLY_BODY,
    INTENT_CONFIRM_SEND_REPLY,
    INTENT_CANCEL_REPLY,
    INTENT_EDIT_REPLY,
    INTENT_START_REMINDER_CREATE,
    INTENT_CAPTURE_REMINDER_DATETIME,
    INTENT_CONFIRM_CREATE_REMINDER,
    INTENT_CANCEL_REMINDER_CREATE,
    INTENT_TODAY_SUMMARY,
    INTENT_UNKNOWN,
    LOOKUP_FIRST,
    LOOKUP_KEYWORD,
    LOOKUP_LAST,
    LOOKUP_LATEST,
    LOOKUP_SENDER,
    LOOKUP_SUBJECT,
    parse_voice_intent,
)


def test_detail_email_intents() -> None:
    cases = [
        ("explain email number 1", 1),
        ("explain email one", 1),
        ("read second mail", 2),
        ("what is email 3 about", 3),
        ("describe the fourth email", 4),
    ]
    for transcript, expected_ref in cases:
        parsed = parse_voice_intent(transcript)
        assert parsed.intent == INTENT_DETAIL_EMAIL
        assert parsed.email_reference == expected_ref
        assert parsed.confidence >= 0.8

    ordinal_phrase = parse_voice_intent("tell me more about first email")
    assert ordinal_phrase.intent == INTENT_DETAIL_EMAIL
    assert ordinal_phrase.lookup_type == LOOKUP_FIRST


def test_sender_keyword_subject_and_ordinal_lookup_metadata() -> None:
    sender_cases = [
        ("explain the email from Google", "google"),
        ("read mail from Amazon", "amazon"),
        ("tell me about message from college", "college"),
    ]
    for transcript, expected_query in sender_cases:
        parsed = parse_voice_intent(transcript)
        assert parsed.intent == INTENT_DETAIL_EMAIL
        assert parsed.lookup_type == LOOKUP_SENDER
        assert parsed.sender_query == expected_query
        assert parsed.lookup_query == expected_query

    keyword_cases = [
        ("explain Kaggle notebook email", "kaggle notebook"),
        ("tell me about assignment mail", "assignment"),
        ("read project email", "project"),
        ("explain auto sync test email", "auto sync test"),
    ]
    for transcript, expected_query in keyword_cases:
        parsed = parse_voice_intent(transcript)
        assert parsed.intent == INTENT_DETAIL_EMAIL
        assert parsed.lookup_type in {LOOKUP_KEYWORD, LOOKUP_SUBJECT}
        assert expected_query in (parsed.lookup_query or "")

    ordinal_cases = [
        ("read latest email", LOOKUP_LATEST),
        ("explain first mail", LOOKUP_FIRST),
        ("read last email", LOOKUP_LAST),
    ]
    for transcript, expected_lookup_type in ordinal_cases:
        parsed = parse_voice_intent(transcript)
        assert parsed.intent == INTENT_DETAIL_EMAIL
        assert parsed.lookup_type == expected_lookup_type


def test_repeat_summary_intents() -> None:
    for transcript in ["repeat", "say again", "I did not understand", "repeat summary"]:
        parsed = parse_voice_intent(transcript)
        assert parsed.intent == INTENT_REPEAT_SUMMARY


def test_end_call_intents() -> None:
    for transcript in ["no", "no need", "end call", "stop", "goodbye", "that's all"]:
        parsed = parse_voice_intent(transcript)
        assert parsed.intent == INTENT_END_CALL


def test_false_positive_no_as_know() -> None:
    for transcript in ["I want to know more", "notebook email", "notification mail", "another email"]:
        parsed = parse_voice_intent(transcript)
        assert parsed.intent == INTENT_UNKNOWN


def test_help_intents() -> None:
    for transcript in ["help", "what can I say", "what are my options"]:
        parsed = parse_voice_intent(transcript)
        assert parsed.intent == INTENT_HELP


def test_today_summary_intents() -> None:
    for transcript in ["what emails did I receive today", "tell me today's mails"]:
        parsed = parse_voice_intent(transcript)
        assert parsed.intent == INTENT_TODAY_SUMMARY


def test_important_check_intents() -> None:
    for transcript in ["anything important", "any urgent mail", "what should I check first"]:
        parsed = parse_voice_intent(transcript)
        assert parsed.intent == INTENT_IMPORTANT_CHECK


def test_unknown_intent() -> None:
    parsed = parse_voice_intent("random unrelated sentence")
    assert parsed.intent == INTENT_UNKNOWN


def test_reply_intents() -> None:
    start_cases = [
        "reply to this email",
        "send a reply",
        "respond to this mail",
        "reply to email number one",
        "reply to the latest email",
        "reply to the Google email",
        "reply saying I will submit it tomorrow",
        "respond with thank you I will check it",
    ]
    for transcript in start_cases:
        parsed = parse_voice_intent(transcript)
        assert parsed.intent == INTENT_START_EMAIL_REPLY

    say_case = parse_voice_intent("tell them I will join the meeting")
    assert say_case.intent == INTENT_UNKNOWN

    confirm_cases = ["yes", "yes send it", "send it", "confirm", "okay send"]
    for transcript in confirm_cases:
        parsed = parse_voice_intent(transcript)
        assert parsed.intent == INTENT_CONFIRM_SEND_REPLY

    cancel_cases = ["cancel", "don't send", "discard", "stop sending"]
    for transcript in cancel_cases:
        parsed = parse_voice_intent(transcript)
        assert parsed.intent == INTENT_CANCEL_REPLY

    edit_cases = ["edit it", "change it", "modify reply"]
    for transcript in edit_cases:
        parsed = parse_voice_intent(transcript)
        assert parsed.intent == INTENT_EDIT_REPLY

    body_case = parse_voice_intent("reply saying I will submit it tomorrow")
    assert body_case.reply_body == "i will submit it tomorrow"

    latest_case = parse_voice_intent("reply to the latest email")
    assert latest_case.target_lookup_type == LOOKUP_LATEST

    number_case = parse_voice_intent("reply to email number one saying I will submit it tomorrow")
    assert number_case.intent == INTENT_START_EMAIL_REPLY
    assert number_case.target_email_reference == 1


def test_reminder_intents() -> None:
    start_cases = [
        "remind me about email number 1 tomorrow at 3 pm",
        "create reminder for this email on monday at 10 am",
        "set a reminder",
    ]
    for transcript in start_cases:
        parsed = parse_voice_intent(transcript)
        assert parsed.intent == INTENT_START_REMINDER_CREATE

    capture_case = parse_voice_intent("tomorrow at 3 pm")
    assert capture_case.intent in {INTENT_START_REMINDER_CREATE, INTENT_UNKNOWN}

    parsed_yes = parse_voice_intent("yes")
    assert parsed_yes.intent in {INTENT_CONFIRM_CREATE_REMINDER, INTENT_CONFIRM_SEND_REPLY}

    cancel_cases = ["cancel reminder", "no", "stop"]
    parsed_no = parse_voice_intent("no")
    assert parsed_no.intent in {INTENT_CANCEL_REMINDER_CREATE, INTENT_END_CALL}
