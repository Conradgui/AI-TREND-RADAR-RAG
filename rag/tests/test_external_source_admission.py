"""Behavior tests for claim-aware external source admission."""

from types import SimpleNamespace

from rag.external_source_admission import infer_claim_type, infer_evidence_demand, review_external_candidates


TODAY = "2026-08-06"


def test_claim_type_is_inferred_from_query_intent_without_closed_whitelist_failure():
    assert infer_claim_type(SimpleNamespace(intent="product_update", task_mode="general", original_question="")) == "product_release"
    assert infer_claim_type(SimpleNamespace(intent="learning_map", task_mode="timeline", original_question="")) == "research"
    assert infer_claim_type(SimpleNamespace(intent="unknown", task_mode="general", original_question="long-tail")) == "unclassified"


def test_recent_source_verification_requires_primary_page_fetch():
    plan = SimpleNamespace(
        intent="recent_trend",
        task_mode="source_check",
        original_question="请核实 OpenAI 过去 7 天官方发布",
        time_window={"label": "last_7_days", "days": 7},
    )

    assert infer_evidence_demand(plan) == "verify_recent_primary"


def test_truthfulness_verification_language_requires_primary_page_fetch():
    plan = SimpleNamespace(
        intent="general_search",
        task_mode="source_check",
        original_question="请验证这条信息的真实性与可靠性",
        time_window={"label": "unspecified", "days": None},
    )

    assert infer_evidence_demand(plan) == "verify_primary_source"


def test_official_release_is_primary_for_vendor_release_claim():
    review = review_external_candidates(
        [{
            "title": "Model release",
            "url": "https://openai.com/index/model-release",
            "source": "OpenAI",
            "source_quality": "official",
            "date_published": "2026-08-04",
            "excerpt": "OpenAI announced the model release.",
        }],
        claim_type="product_release",
        today=TODAY,
    )

    assert review["admitted"][0]["source_role"] == "primary_claim_source"
    assert review["admitted"][0]["admission_action"] == "admit"
    assert review["admitted"][0]["date_status"] == "verified"


def test_official_navigation_page_is_not_admitted_as_a_release_record():
    review = review_external_candidates(
        [
            {
                "title": "OpenAI Newsroom | Product | OpenAI",
                "url": "https://openai.com/news/product-releases/",
                "source": "openai.com",
                "source_quality": "official",
                "published_at": "2026-08-04T06:35:03Z",
                "excerpt": "Product release listing page",
            }
        ],
        claim_type="product_release",
        recent_required=True,
        recent_window_days=7,
        today="2026-08-06",
    )

    assert review["admitted"] == []
    reference = review["search_references"][0]
    assert reference["document_role"] == "navigation_page"
    assert reference["date_status"] == "missing"
    assert reference["not_admitted_reason"] == "navigation_page_only"


def test_vendor_page_cannot_independently_prove_market_leadership():
    review = review_external_candidates(
        [{
            "title": "We are the leader",
            "url": "https://vendor.example.com/leader",
            "source": "Vendor",
            "source_quality": "official",
            "date_published": "2026-08-05",
            "excerpt": "The vendor says it leads the market.",
        }],
        claim_type="market_evaluation",
        today=TODAY,
    )

    assert review["admitted"] == []
    assert review["search_references"][0]["source_role"] == "supporting_context"
    assert review["search_references"][0]["admission_action"] == "downgrade"


def test_recent_query_moves_old_or_undated_material_to_search_references():
    review = review_external_candidates(
        [
            {
                "title": "Old announcement",
                "url": "https://example.com/old",
                "source_quality": "primary",
                "date_published": "2024-07-01",
            },
            {
                "title": "Unknown date",
                "url": "https://example.com/unknown",
                "source_quality": "high-signal",
            },
        ],
        claim_type="product_release",
        recent_required=True,
        today=TODAY,
    )

    assert review["admitted"] == []
    assert {item["admission_action"] for item in review["search_references"]} == {"background", "downgrade"}
    assert {item["date_status"] for item in review["search_references"]} == {"verified", "missing"}


def test_unsafe_url_and_directly_unsupported_content_are_excluded():
    review = review_external_candidates(
        [
            {"title": "Local", "url": "http://127.0.0.1/admin", "excerpt": "secret"},
            {"title": "Mismatch", "url": "https://example.com/x", "supports_claim": False},
        ],
        claim_type="product_release",
        today=TODAY,
    )

    assert review["admitted"] == []
    assert [item["exclusion_reason"] for item in review["excluded"]] == ["unsafe_url", "content_does_not_support_claim"]


def test_same_canonical_url_can_only_enter_one_final_source_group():
    review = review_external_candidates(
        [
            {"title": "Release", "url": "https://example.com/release?utm_source=x", "date_published": "2026-08-05"},
            {"title": "Release copy", "url": "https://example.com/release", "date_published": "2026-08-05"},
        ],
        claim_type="product_release",
        today=TODAY,
    )

    all_urls = [item["canonical_url"] for group in ("admitted", "search_references", "excluded") for item in review[group]]
    assert all_urls.count("https://example.com/release") == 1
