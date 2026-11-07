import csv
import io
import json

import pytest

from app.services.combat_simulator import (
    BattleScenario,
    CombatantSpec,
    SkillSpec,
    SYNTHETIC_SCENARIOS,
    _choose_party_candidate,
    run_batch,
)
from app.services.combat_strategies import candidate_sort_key
from app.services.combat_ai_strategy_comparison import (
    POLICY_VERSION,
    STRATEGIES,
    build_experimental_scenarios,
    report_to_csv,
    report_to_markdown,
    run_ai_strategy_comparison,
)


def _key(strategy: str, **kwargs):
    return candidate_sort_key(
        strategy,
        kills_target=kwargs.get("kills_target", False),
        effective_damage=kwargs.get("effective_damage", 10),
        mana_cost=kwargs.get("mana_cost", 3),
        raw_damage=kwargs.get("raw_damage", 10),
        target_hp=kwargs.get("target_hp", 20),
        elemental_weakness=kwargs.get("elemental_weakness", False),
        skill_id=kwargs.get("skill_id", "skill"),
        target_id=kwargs.get("target_id", "target"),
        current_mana=kwargs.get("current_mana"),
        max_mana=kwargs.get("max_mana"),
        target_threat=kwargs.get("target_threat", 0),
        applies_new_effect=kwargs.get("applies_new_effect", False),
    )


def test_six_policy_scorers_encode_distinct_selection_priorities() -> None:
    assert _key("baseline", kills_target=True) == (
        -1,
        -10,
        3,
        -10,
        0,
        "skill",
        "target",
    )
    assert _key("aggressive", kills_target=True)[0] < _key(
        "aggressive", kills_target=False
    )[0]
    assert _key("conservative", target_threat=20)[1] < _key(
        "conservative", target_threat=10
    )[1]
    assert _key("economic", mana_cost=2)[0] < _key("economic", mana_cost=8)[0]
    assert _key("tactical", elemental_weakness=True)[0] < _key(
        "tactical", elemental_weakness=False
    )[0]
    assert _key("tactical", applies_new_effect=True)[1] < _key(
        "tactical", applies_new_effect=False
    )[1]
    assert _key("adaptive", current_mana=2, max_mana=20, mana_cost=2)[1] < _key(
        "adaptive", current_mana=2, max_mana=20, mana_cost=8
    )[1]
    assert _key(
        "adaptive",
        current_mana=18,
        max_mana=20,
        elemental_weakness=True,
    )[1] < _key(
        "adaptive",
        current_mana=18,
        max_mana=20,
        elemental_weakness=False,
    )[1]


def test_candidate_selector_handles_no_valid_actions() -> None:
    assert _choose_party_candidate([], "aggressive") is None


@pytest.mark.anyio
async def test_all_policies_run_on_authoritative_simulator_and_replay() -> None:
    scenario = BattleScenario(
        "h14-policy-target-selection",
        "H.14 synthetic policy target selection",
        (
            CombatantSpec(
                "Alvo vulnerável",
                "player",
                8,
                100,
                0,
                1,
                speed=1,
                weaknesses=("fire",),
            ),
            CombatantSpec(
                "Inimigo estrategista",
                "enemy",
                8,
                200,
                20,
                4,
                magic_attack=12,
                speed=8,
                skills=(
                    SkillSpec("Chama fraca", "magic", 1, 4, "fire"),
                    SkillSpec("Orbe forte", "magic", 20, 4, "arcane"),
                ),
            ),
        ),
        max_turns=4,
    )
    results = {}
    for strategy in STRATEGIES:
        batch = await run_batch(
            scenario,
            [88],
            party_strategy="effective_damage",
            enemy_strategy=strategy,
        )
        assert batch["failures"] == []
        results[strategy] = batch["results"][0]
        assert results[strategy]["rules_version"] == "h4-authoritative+h7-combat-rules"
        assert results[strategy]["invalid_action_count"] is None
        assert results[strategy]["target_selections"]["enemy"]

    baseline_first = next(
        event["payload"]
        for event in results["baseline"]["events"]
        if event["type"] == "action_resolved"
        and event["payload"]["actor_id"]
        == next(
            participant["combatant_id"]
            for participant in results["baseline"]["participants"]
            if participant["side"] == "enemy"
        )
    )
    tactical_first = next(
        event["payload"]
        for event in results["tactical"]["events"]
        if event["type"] == "action_resolved"
        and event["payload"]["actor_id"]
        == next(
            participant["combatant_id"]
            for participant in results["tactical"]["participants"]
            if participant["side"] == "enemy"
        )
    )
    assert baseline_first["skill_id"] is not None
    assert tactical_first["skill_id"] is not None
    assert baseline_first["skill_id"] == results["baseline"]["skills"]["Orbe forte"][
        "skill_id"
    ]
    assert tactical_first["skill_id"] == results["tactical"]["skills"]["Chama fraca"][
        "skill_id"
    ]

    again = await run_batch(
        scenario,
        [88],
        party_strategy="effective_damage",
        enemy_strategy="tactical",
    )
    assert results["tactical"] == again["results"][0]


@pytest.mark.anyio
async def test_paired_report_exports_consistent_scenario_data() -> None:
    report = await run_ai_strategy_comparison(
        scenarios=(SYNTHETIC_SCENARIOS["low-vs-basic"],),
        seeds=(140, 141),
    )

    assert report["source"] == "synthetic-only"
    assert report["canonical_ai_replaced"] is False
    assert report["policy_version"] == POLICY_VERSION
    assert report["strategies"] == list(STRATEGIES)
    assert report["battle_count"] == 12
    scenario = report["scenarios"][0]
    assert set(scenario["strategies"]) == set(STRATEGIES)
    assert all(
        details["aggregate"]["sample_size"] == 2
        for details in scenario["strategies"].values()
    )
    assert all(
        comparison["pair_count"] == 2
        for comparison in scenario["paired_vs_baseline"].values()
    )
    assert report["simulation_failure_count"] == 0

    markdown = report_to_markdown(report)
    rows = list(csv.DictReader(io.StringIO(report_to_csv(report))))
    assert "Limitações estatísticas" in markdown
    assert "declarada superior" in markdown
    assert "Com mana acima de 25%" in markdown
    assert len(rows) == report["battle_count"]
    assert {row["strategy"] for row in rows} == set(STRATEGIES)
    assert {row["seed"] for row in rows} == {"140", "141"}
    assert all(row["invalid_action_count"] == "" for row in rows)


@pytest.mark.anyio
async def test_experimental_policies_use_threat_mana_and_effect_context() -> None:
    scenarios = {item.scenario_id: item for item in build_experimental_scenarios()}
    threat_scenario = scenarios["h14-elemental-threat"]
    conservative = await run_batch(
        threat_scenario, [141], party_strategy="effective_damage",
        enemy_strategy="conservative",
    )
    conservative_event = next(
        event["payload"]
        for event in conservative["results"][0]["events"]
        if event["type"] == "action_resolved"
        and event["payload"]["actor_id"]
        == next(
            item["combatant_id"]
            for item in conservative["results"][0]["participants"]
            if item["side"] == "enemy"
        )
    )
    target_id = conservative_event["target_id"]
    target_name = next(
        item["name"]
        for item in conservative["results"][0]["participants"]
        if item["combatant_id"] == target_id
    )
    assert target_name == "Alvo resistente"

    mana_scenario = scenarios["h14-mana-budget"]
    baseline = await run_batch(
        mana_scenario, [142], enemy_strategy="baseline"
    )
    economic = await run_batch(
        mana_scenario, [142], enemy_strategy="economic"
    )
    assert economic["results"][0]["total_mana_consumed"] < baseline["results"][0][
        "total_mana_consumed"
    ]

    effect_scenario = scenarios["h14-effect-priority"]
    tactical = await run_batch(effect_scenario, [143], enemy_strategy="tactical")
    tactical_skills = tactical["results"][0]["skills"]
    assert tactical_skills["Toxina persistente"]["uses"] > 0
    assert tactical_skills["Toxina persistente"]["effect_application_count"] > 0

    report = await run_ai_strategy_comparison(
        scenarios=(effect_scenario,),
        seeds=(143,),
    )
    tactical_summary = report["scenarios"][0]["strategies"]["tactical"]["aggregate"]
    assert tactical_summary["enemy_skill_usage"]["Toxina persistente"]["uses"] > 0
    assert "Toxina persistente" in report_to_markdown(report)
    csv_rows = list(csv.DictReader(io.StringIO(report_to_csv(report))))
    tactical_row = next(row for row in csv_rows if row["strategy"] == "tactical")
    assert (
        json.loads(tactical_row["enemy_skill_usage"])["Toxina persistente"]["uses"]
        > 0
    )
