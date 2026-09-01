from rag.entity_identity import (
    canonical_entity_id,
    query_entity_ids,
    related_entity_expansions,
)


def test_registry_keeps_products_and_organizations_distinct():
    assert canonical_entity_id("Gemini") == "gemini"
    assert canonical_entity_id("Google") == "google"
    assert canonical_entity_id("Google DeepMind") == "google-deepmind"
    assert canonical_entity_id("Grok") == "grok"
    assert canonical_entity_id("xAI") == "xai"


def test_registry_has_bounded_verified_expansions_for_gemini_and_grok():
    gemini = related_entity_expansions(["Gemini"])
    grok = related_entity_expansions(["Grok"])
    assert {item["entity_id"] for item in gemini} == {"google-deepmind", "google"}
    assert {item["entity_id"] for item in grok} == {"xai", "x"}
    assert all(0 < item["weight"] < 1 for item in gemini + grok)


def test_ambiguous_antigravity_and_spacex_do_not_expand_automatically():
    assert related_entity_expansions(["Antigravity"]) == []
    assert related_entity_expansions(["SpaceX"]) == []


def test_grok_bot_is_a_product_variant_not_an_alias_for_xai():
    assert canonical_entity_id("Grok Bot") == "grok-bot"
    assert related_entity_expansions(["Grok Bot"]) == [
        {
            "from_entity_id": "grok-bot",
            "entity_id": "grok",
            "relation": "product_of",
            "weight": 0.65,
        }
    ]


def test_repository_slug_does_not_invent_a_product_entity() -> None:
    assert query_entity_ids(
        "Graphify 和 claude-mem 在保留和检索上下文上分别做什么？"
    ) == []
