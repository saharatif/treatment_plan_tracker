from app.ids import generate_orb_ref, generate_token


def test_generate_token_is_unique_and_normalized():
    first = generate_token()
    second = generate_token()

    assert first != second
    assert first.startswith("tok_")
    assert second.startswith("tok_")
    assert len(first) == len(second) == 20


def test_generate_orb_ref_uses_patient_suffix():
    assert generate_orb_ref("PAT-2025-00847", 3) == "ORB-PAT00847-003"
