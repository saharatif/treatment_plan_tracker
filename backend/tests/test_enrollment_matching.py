from app.services.enrollment import normalize_codes, score_catalog_match


class CatalogOrb:
    def __init__(self, catalog_code, title, category, billing_codes):
        self.catalog_code = catalog_code
        self.title = title
        self.category = category
        self.billing_codes = billing_codes


def test_normalize_codes_strips_system_prefixes():
    assert normalize_codes(["CPT: 83036", " icd-10: e11.9 ", "A4253"]) == {
        "83036",
        "E11.9",
        "A4253",
    }


def test_score_catalog_match_favors_code_and_category_match():
    parsed = {
        "title": "Blood Work Baseline",
        "category": "Lab",
        "billing_codes": ["CPT: 83036"],
    }
    catalog = CatalogOrb("LAB-01", "Blood Work - Baseline Labs", "Lab", ["83036", "80053"])

    assert score_catalog_match(parsed, catalog) >= 0.72


def test_score_catalog_match_accepts_direct_catalog_code():
    parsed = {"title": "Daily vitamins", "catalog_code": "VIT-01"}
    catalog = CatalogOrb("VIT-01", "Daily Multivitamin Protocol", "Vitamins", [])

    assert score_catalog_match(parsed, catalog) >= 1.0
