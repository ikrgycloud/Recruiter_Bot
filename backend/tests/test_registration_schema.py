from app.schemas.auth import RegisterRequest


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
