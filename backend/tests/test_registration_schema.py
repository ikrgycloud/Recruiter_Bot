from unittest.mock import MagicMock, patch

from app.schemas.auth import RegisterRequest
from app.services.google_workspace import classify_message, infer_reschedule_window, list_message_ids


def test_register_request_needs_only_employee_name_and_email():
    payload = RegisterRequest(
        full_name="Jane Recruiter",
        company_email="jane@acme.com",
        password="password123",
        confirm_password="password123",
    )

    assert payload.company_email == "jane@acme.com"
    assert payload.company_name is None
    assert payload.full_name == "Jane Recruiter"


def test_list_message_ids_reads_entire_inbox_when_max_results_is_unlimited():
    mock_service = MagicMock()
    mock_service.users.return_value.messages.return_value.list.side_effect = [
        MagicMock(execute=MagicMock(return_value={"messages": [{"id": "a"}, {"id": "b"}], "nextPageToken": "page-2"})),
        MagicMock(execute=MagicMock(return_value={"messages": [{"id": "c"}]})),
    ]

    with patch("app.services.google_workspace.build", return_value=mock_service):
        ids = list_message_ids(credentials=None, max_results=None)

    assert ids == ["a", "b", "c"]


def test_classify_message_uses_full_email_body_text():
    full_text = "Hi team, I am unable to attend and need to reschedule my interview to next Tuesday afternoon."

    assert classify_message("Interview request", full_text) == "reschedule_request"
    assert classify_message("General update", "Everything looks fine") == "other"


def test_classify_message_handles_reschedule_phrase_without_ai():
    body = "Can I reschedule my meeting from 22/09/2026 to 28/09/2026 please let me know if that's possible, if it is can you please do that for me. Thank you"

    assert classify_message("Meeting request", body) == "reschedule_request"


def test_classify_message_ignores_google_security_notices():
    body = "You allowed Interview Reschedule Bot access to some of your Google Account data. If you didn't allow ... Check activity."

    assert classify_message("Google Account Security", body) == "other"


def test_classify_message_detects_reschedule_from_subject_line():
    assert classify_message("Rescheduling interview time", "Hi, can we meet next Tuesday?") == "reschedule_request"
    assert classify_message("Changing interview schedule", "Thanks") == "reschedule_request"


def test_infer_reschedule_window_reads_candidate_date_from_message():
    start, end = infer_reschedule_window("Interview update", "Can we move the interview to 28/09/2026? Please confirm.")

    assert start is not None
    assert end is not None
    assert start.date().isoformat() == "2026-09-28"
    assert end.date().isoformat() == "2026-09-28"
