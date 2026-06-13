from app.services.billing import collect_billing_codes, normalize_billing_code


def test_normalize_billing_code_strips_prefix():
    assert normalize_billing_code("CPT: 83036") == "83036"
    assert normalize_billing_code(" icd-10: e11.9 ") == "E11.9"


def test_collect_billing_codes_keeps_sources_and_unifies_duplicates_per_source():
    plan = {
        "diagnoses": [{"code": "E11.9"}, {"code": "E11.9"}],
        "orbs": [
            {"orb_number": 1, "billing_codes": ["CPT: 83036", "80053"]},
            {"orb_number": 1, "billing_codes": ["83036"]},
            {"orb_number": 2, "billing_codes": ["83036"]},
        ],
    }

    assert collect_billing_codes(plan) == [
        {"code": "E11.9", "source": "diagnosis"},
        {"code": "83036", "source": "orb_1"},
        {"code": "80053", "source": "orb_1"},
        {"code": "83036", "source": "orb_2"},
    ]
