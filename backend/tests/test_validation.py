from app.services.validation import validate_parsed_plan


def _valid_plan():
    return {
        "plan_id": "PLN-2026-003",
        "patient_id": "PAT-2026-00847",
        "plan_start": "2026-06-13",
        "orbs": [
            {
                "orb_number": number,
                "title": f"Orb {number}",
                "target_date": "2026-06-13",
                "billing_codes": [],
            }
            for number in range(1, 11)
        ],
    }


def test_validate_parsed_plan_accepts_required_shape():
    assert validate_parsed_plan(_valid_plan()) == (True, [])


def test_validate_parsed_plan_rejects_missing_orbs_and_ids():
    is_valid, errors = validate_parsed_plan({"orbs": []})

    assert not is_valid
    assert "Expected 10 orbs, found 0" in errors
    assert "Missing required field: plan_id" in errors


def test_validate_parsed_plan_rejects_bad_orb_number_sequence():
    plan = _valid_plan()
    plan["orbs"][0]["orb_number"] = 9

    is_valid, errors = validate_parsed_plan(plan)

    assert not is_valid
    assert any(error.startswith("Orb numbers not 1-10") for error in errors)
