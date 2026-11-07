import csv
from dataclasses import replace
import io
import json

import pytest

from app.services.combat_simulator import run_batch
from app.services.combat_skill_balance_analysis import (
    SEED,
    build_ai_cases,
    build_skill_cases,
    classify_skill,
    report_to_csv,
    report_to_markdown,
    run_skill_balance_analysis,
)


def _case(skill_name: str, context_id: str):
    return next(
        case
        for case in build_skill_cases()
        if case.skill.name == skill_name and case.context_id == context_id
    )


def test_skill_comparisons_hold_all_initial_conditions_constant() -> None:
    case = _case("Orbe arcano", "resistant")
    control_player = case.control.participants[0]
    comparison_player = case.comparison.participants[0]
    control_target, comparison_target = case.control.participants[1], case.comparison.participants[1]

    assert control_player.skills == ()
    assert comparison_player.skills == (case.skill,)
    assert replace(control_player, skills=(case.skill,)) == comparison_player
    assert control_target == comparison_target
    assert case.control.max_turns == case.comparison.max_turns


def test_classifier_does_not_overstate_small_or_zero_samples() -> None:
    insufficient = classify_skill([])
    assert insufficient["classification"] == "dados insuficientes"

    no_uses = [
        {
            "context_id": f"context-{index}",
            "skill_metrics": {"uses": 0},
            "round_reduction_fraction": 0.0,
            "party_damage_delta_fraction": 0.0,
            "paired_benefit": False,
            "paired_disadvantage": False,
            "control": {"result": "victory"},
            "comparison": {"result": "victory"},
        }
        for index in range(5)
    ]
    assert classify_skill(no_uses)["classification"] == "dados insuficientes"


@pytest.mark.anyio
async def test_h13_generates_skill_ai_and_export_evidence() -> None:
    report = await run_skill_balance_analysis()

    assert report["source"] == "synthetic-only"
    assert report["canonical_catalog_accessed"] is False
    assert report["seed"] == SEED
    assert len(report["comparisons"]) == len(build_skill_cases())
    assert len(report["skills"]) == 6
    assert all(
        skill["classification"]["classification"]
        in {
            "potencialmente dominante",
            "potencialmente forte",
            "dentro da faixa comparativa",
            "potencialmente fraca",
            "dados insuficientes",
        }
        for skill in report["skills"]
    )

    poison = next(item for item in report["skills"] if item["skill"] == "Veneno gradual")
    assert poison["metrics"]["effect_applications"] > 0
    assert poison["metrics"]["damage_over_time_attribution"] is None

    healing = next(
        item for item in report["skills"] if item["skill"] == "Restauração sintética"
    )
    assert healing["metrics"]["healing"] > 0
    assert healing["metrics"]["damage_per_mana"] is None
    assert healing["metrics"]["healing_per_mana"] > 0
    assert healing["metrics"]["hit_rate"] is None
    heal_context = next(
        row
        for row in report["comparisons"]
        if row["skill"] == "Restauração sintética"
    )
    assert heal_context["comparison"]["wounded_ally_hp_final"] > 10

    constrained = next(
        row
        for row in report["comparisons"]
        if row["skill"] == "Técnica de mana restrita"
    )
    assert constrained["skill_metrics"]["uses"] == 0
    assert constrained["skill_initially_eligible"] is False

    ai_cases = build_ai_cases()
    fire_choices = [
        observation
        for observation in report["ai_observations"]
        if observation["case_id"] == "enemy-elemental-choice"
    ]
    assert len(fire_choices) == len(ai_cases[0].strategies)
    assert {
        observation["strategy"] for observation in fire_choices
    } == {"baseline", "elemental_weakness"}
    assert all(observation["first_turn_eligible_skills"] for observation in fire_choices)
    assert all(
        observation["first_turn_selection_frequency_by_skill"]
        for observation in fire_choices
    )
    assert {
        observation["strategy"]: observation["first_enemy_action_skill"]
        for observation in fire_choices
    } == {
        "baseline": "Projétil arcano",
        "elemental_weakness": "Explosão de fogo",
    }

    markdown = report_to_markdown(report)
    rows = list(csv.DictReader(io.StringIO(report_to_csv(report))))
    assert "Limitações" in markdown
    assert "não representa o catálogo canônico" in markdown
    assert len(rows) == len(report["comparisons"])
    assert rows[0]["battle_count"] == "1"
    assert rows[0]["hit_rate"] == ""
    assert json.loads(json.dumps(report, ensure_ascii=False))["source"] == "synthetic-only"


@pytest.mark.anyio
async def test_seed_replays_the_same_h13_controlled_skill_battle() -> None:
    case = _case("Chama controlada", "weak")
    first = await run_batch(case.comparison, (SEED,))
    second = await run_batch(case.comparison, (SEED,))

    assert first["failures"] == second["failures"] == []
    assert first["results"] == second["results"]
