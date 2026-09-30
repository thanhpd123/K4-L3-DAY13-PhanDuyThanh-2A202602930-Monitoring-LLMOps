from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd() -> None:
    out = scrub_text("CCCD cua toi la 012345678901")
    assert "012345678901" not in out
    assert "REDACTED_CCCD" in out


def test_scrub_credit_card_in_common_formats() -> None:
    card_numbers = (
        "4111 1111 1111 1111",
        "4111-1111-1111-1111",
        "4111111111111111",
    )

    for card_number in card_numbers:
        out = scrub_text(f"The cua toi: {card_number}")
        assert card_number not in out
        assert "REDACTED_CREDIT_CARD" in out


def test_scrub_vietnamese_address() -> None:
    out = scrub_text("Địa chỉ: 12 Nguyễn Trãi, Quận 1")
    assert "12 Nguyễn Trãi" not in out
    assert "REDACTED_ADDRESS_VN" in out

    unaccented = scrub_text("Dia chi: 12 Nguyen Trai, Quan 1")
    assert "12 Nguyen Trai" not in unaccented
    assert "REDACTED_ADDRESS_VN" in unaccented


def test_scrub_cmnd_and_passport() -> None:
    assert "123456789" not in scrub_text("CMND: 123456789")
    assert "REDACTED_CMND" in scrub_text("CMND: 123456789")

    assert "B1234567" not in scrub_text("Passport: B1234567")
    assert "REDACTED_PASSPORT_VN" in scrub_text("Passport: B1234567")
