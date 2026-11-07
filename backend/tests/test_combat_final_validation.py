from app.services.combat_final_validation import (
    aggregate_rows,
    audit_recommendation_evidence,
    report_to_csv,
)


def test_final_aggregates_remain_descriptive_and_seed_scoped() -> None:
    rows = [
        {
            "stage": "H.12",
            "scenario_id": "defense-control",
            "strategy": "baseline",
            "seed": seed,
            "result": "victory",
            "turns": 7,
            "logical_duration_rounds": 4,
            "actions_executed": 7,
            "party_survival_rate": 1.0,
            "party_damage_effective": 19,
            "party_damage_received_effective": 3,
            "party_healing_effective": 0,
            "party_mana_consumed": 0,
        }
        for seed in (100, 101, 102)
    ]

    summary = aggregate_rows(rows)

    assert summary["sample_size"] == 3
    assert summary["outcome_counts"]["victory"] == 3
    assert summary["win_rate"] == 1
    assert summary["metrics"]["turns"]["mean"] == 7
    assert summary["metrics"]["turns"]["median"] == 7
    assert summary["metrics"]["turns"]["population_stddev"] == 0
    assert summary["metrics"]["party_survival_rate"]["mean"] == 1
    assert summary["metrics"]["enemy_mana_consumed"]["missing_count"] == 3
    assert summary["seed_values"] == [100, 101, 102]
    assert summary["distinct_metric_values"]["party_damage_effective"] == 1


def test_h15_recommendations_are_audited_without_canonical_changes() -> None:
    recommendations = [
        {
            "id": item_id,
            "priority": "alta",
            "title": item_id,
        }
        for item_id in (
            "synthetic-enemy-defense-threshold",
            "synthetic-boss-party-size-threshold",
            "synthetic-equipment-deltas",
            "synthetic-direct-skill-efficiency",
            "h14-policy-outcomes",
            "canonical-catalog-unassessed",
        )
    ]

    audited = audit_recommendation_evidence(
        {"recommendations": recommendations}
    )

    assert len(audited) == 6
    assert all(item["action_taken"] == "none" for item in audited)
    assert all(not item["canonical_changes_authorized"] for item in audited)
    assert all(
        item["evidence_grade"] in {
            "insufficient-for-change",
            "no-official-change",
            "pending-authorized-catalog",
        }
        for item in audited
    )


def test_csv_exports_battle_level_metrics_without_dropping_skill_effects() -> None:
    report = {
        "final_simulations": {
            "battle_rows": [
                {
                    "stage": "H.14",
                    "scenario_id": "synthetic-effect",
                    "strategy": "tactical",
                    "seed": 143,
                    "result": "turn_limit",
                    "turns": 10,
                    "logical_duration_rounds": 10,
                    "actions_executed": 15,
                    "party_survivors": 1,
                    "party_defeated": 0,
                    "party_hp_remaining": 80,
                    "party_damage_effective": 60,
                    "party_damage_received_effective": 100,
                    "party_mana_consumed": 0,
                    "party_healing_effective": 0,
                    "enemy_survivors": 1,
                    "enemy_defeated": 0,
                    "enemy_hp_remaining": 40,
                    "enemy_damage_effective": 100,
                    "enemy_damage_received_effective": 60,
                    "enemy_mana_consumed": 24,
                    "enemy_healing_effective": 0,
                    "effect_applications": 4,
                    "skills": {"Toxina": {"uses": 2, "effect_application_count": 4}},
                    "target_selections": {"enemy": {"Defensor": 5}},
                    "action_selections": {"enemy": {"skill": 2}},
                    "invalid_action_count": None,
                    "simulator_version": "1.0.0",
                    "rules_version": "h4-authoritative+h7-combat-rules",
                }
            ]
        }
    }

    lines = report_to_csv(report).splitlines()
    assert len(lines) == 2
    assert "effect_applications" in lines[0]
    assert "Toxina" in lines[1]
    assert "h4-authoritative+h7-combat-rules" in lines[1]
