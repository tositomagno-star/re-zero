import csv
import io

import pytest

from app.services import combat_simulator as simulator
from app.services.combat_simulator import (
    BattleScenario,
    CombatantSpec,
    SkillSpec,
    SYNTHETIC_SCENARIOS,
    aggregate_results,
    compare_strategies,
    export_csv,
    export_json,
    replay_battle,
    run_batch,
    scenario_from_dict,
    scenario_to_dict,
    simulate_battle,
)


def test_scenario_validation_accepts_seven_players() -> None:
    scenario = BattleScenario(
        "seven-player-party",
        "Seven-player party",
        tuple(
            CombatantSpec(f"Hero {index}", "player", 1, 20, 0, 4)
            for index in range(7)
        )
        + (CombatantSpec("Enemy", "enemy", 1, 10, 0, 1),),
    )

    simulator._validate_scenario(scenario)


@pytest.mark.anyio
async def test_simulator_runs_authoritative_combat_and_clips_overkill_metrics() -> None:
    scenario = BattleScenario(
        "metric-overkill",
        "Synthetic overkill metric",
        (
            CombatantSpec("Hero", "player", 1, 20, 0, 4, speed=5),
            CombatantSpec("Target", "enemy", 1, 5, 0, 1, speed=1),
        ),
    )

    result = await simulate_battle(scenario, seed=7)

    hero, target = result["participants"]
    assert result["result"] == "victory"
    assert hero["damage_raw"] == 8
    assert hero["damage_effective"] == 5
    assert hero["damage_received_effective"] == 1
    assert result["total_damage_raw"] == 9
    assert result["total_damage_effective"] == 6
    assert target["hp_final"] == 0
    assert target["rounds_until_defeat"] == 2
    assert result["actions_executed"] == 3


@pytest.mark.anyio
async def test_same_scenario_and_seed_replays_identical_result() -> None:
    scenario = SYNTHETIC_SCENARIOS["special-effects"]
    first = await simulate_battle(scenario, seed=121)
    second = await simulate_battle(scenario, seed=121)

    assert export_json(first) == export_json(second)


@pytest.mark.anyio
async def test_seeds_are_recorded_without_inventing_combat_randomness() -> None:
    scenario = SYNTHETIC_SCENARIOS["low-vs-basic"]
    first = await simulate_battle(scenario, seed=1)
    second = await simulate_battle(scenario, seed=2)

    assert first["seed"] == 1
    assert second["seed"] == 2
    assert first["result"] == second["result"]
    assert first["total_damage_effective"] == second["total_damage_effective"]


@pytest.mark.anyio
async def test_healing_efficiency_mana_and_overheal_are_measured() -> None:
    scenario = BattleScenario(
        "healing-metrics",
        "Healing metrics",
        (
            CombatantSpec(
                "Healer",
                "player",
                3,
                30,
                10,
                1,
                speed=5,
                skills=(
                    SkillSpec(
                        "Mend",
                        "healing",
                        damage_base=8,
                        mana_cost=3,
                        skill_type="heal",
                        target_type="ally",
                        additional_effects={"effect_type": "heal"},
                    ),
                ),
            ),
            CombatantSpec(
                "Wounded",
                "player",
                2,
                30,
                0,
                1,
                speed=4,
                current_hp=10,
            ),
            CombatantSpec("Weak foe", "enemy", 1, 3, 0, 1, speed=1),
        ),
    )

    result = await simulate_battle(scenario, seed=3, party_strategy="survival")
    healer = next(item for item in result["participants"] if item["name"] == "Healer")
    wounded = next(item for item in result["participants"] if item["name"] == "Wounded")
    mend = result["skills"]["Mend"]

    assert healer["mana_consumed"] >= 3
    assert healer["healing_effective"] == mend["healing"]
    assert wounded["hp_final"] > 10
    assert mend["uses"] >= 1
    assert mend["healing"] == 8
    assert mend["damage_per_mana"] == 0
    assert mend["mana_cost"] == 3
    assert mend["healing_per_mana"] == pytest.approx(8 / 3)


@pytest.mark.anyio
async def test_healing_waste_is_not_double_counted_when_target_nearly_full() -> None:
    scenario = BattleScenario(
        "healing-overflow",
        "Healing overflow metrics",
        (
            CombatantSpec(
                "Healer",
                "player",
                3,
                30,
                6,
                1,
                speed=5,
                skills=(
                    SkillSpec(
                        "Small Mend",
                        "healing",
                        damage_base=8,
                        mana_cost=2,
                        skill_type="heal",
                        target_type="ally",
                        additional_effects={"effect_type": "heal"},
                    ),
                ),
            ),
            CombatantSpec(
                "Wounded",
                "player",
                2,
                4,
                0,
                1,
                speed=4,
                current_hp=2,
            ),
            CombatantSpec("Weak foe", "enemy", 1, 3, 0, 1, speed=1),
        ),
    )

    result = await simulate_battle(scenario, seed=4, party_strategy="survival")
    healer = next(item for item in result["participants"] if item["name"] == "Healer")
    wounded = next(item for item in result["participants"] if item["name"] == "Wounded")

    assert healer["healing_effective"] == 2
    assert healer["healing_wasted"] == 6
    assert 2 <= wounded["hp_final"] <= 4
    assert result["total_healing_effective"] == 2
    assert result["total_healing_wasted"] == 6


@pytest.mark.anyio
async def test_turn_limit_is_reported_as_non_victory() -> None:
    result = await simulate_battle(SYNTHETIC_SCENARIOS["limit-draw"], seed=9)

    assert result["result"] == "turn_limit"
    assert result["turns"] == 4
    assert result["logical_duration_rounds"] == 2
    assert result["players_surviving"] == 1
    assert result["enemies_surviving"] == 1
    assert result["events"][-1]["type"] == "simulation_limit_reached"


@pytest.mark.anyio
async def test_strategy_comparison_reuses_the_same_seed_set() -> None:
    report = await compare_strategies(
        SYNTHETIC_SCENARIOS["elemental-weakness"],
        [11, 12],
        strategies=("baseline", "mana_conservation", "elemental_weakness"),
    )

    assert report["seeds"] == [11, 12]
    assert set(report["strategies"]) == {
        "baseline",
        "mana_conservation",
        "elemental_weakness",
    }
    assert all(value["requested"] == 2 for value in report["strategies"].values())
    assert all(not value["failures"] for value in report["strategies"].values())


@pytest.mark.anyio
async def test_experimental_enemy_strategy_changes_resource_tradeoff() -> None:
    scenario = BattleScenario(
        "ai-mana-tradeoff",
        "Enemy AI mana tradeoff",
        (
            CombatantSpec("Durable hero", "player", 8, 120, 0, 1, speed=3),
            CombatantSpec(
                "Spellcaster",
                "enemy",
                8,
                200,
                8,
                1,
                magic_attack=6,
                speed=5,
                skills=(
                    SkillSpec(
                        "Heavy spell",
                        "magic",
                        damage_base=8,
                        mana_cost=4,
                        skill_type="arcane",
                    ),
                ),
            ),
        ),
        max_turns=3,
    )
    baseline = await simulate_battle(
        scenario, seed=31, enemy_strategy="baseline"
    )
    saver = await simulate_battle(
        scenario, seed=31, enemy_strategy="mana_conservation"
    )
    baseline_enemy = next(item for item in baseline["participants"] if item["side"] == "enemy")
    saver_enemy = next(item for item in saver["participants"] if item["side"] == "enemy")

    assert baseline_enemy["mana_consumed"] > saver_enemy["mana_consumed"]
    assert baseline["seed"] == saver["seed"]


@pytest.mark.anyio
async def test_batch_isolates_one_battle_failure_and_reports_progress(monkeypatch) -> None:
    original = simulator._simulate_in_session
    progress: list[tuple[int, int]] = []

    async def fail_one(session_factory, scenario, *, seed, party_strategy, enemy_strategy):
        if seed == 5:
            raise RuntimeError("synthetic isolated failure")
        return await original(
            session_factory,
            scenario,
            seed=seed,
            party_strategy=party_strategy,
            enemy_strategy=enemy_strategy,
        )

    monkeypatch.setattr(simulator, "_simulate_in_session", fail_one)
    report = await run_batch(
        SYNTHETIC_SCENARIOS["low-vs-basic"],
        [4, 5, 6],
        progress=lambda done, total: progress.append((done, total)),
    )

    assert len(report["results"]) == 2
    assert report["failures"] == [
        {
            "scenario_id": "low-vs-basic",
            "seed": 5,
            "error_type": "RuntimeError",
            "message": "synthetic isolated failure",
        }
    ]
    assert progress == [(1, 3), (2, 3), (3, 3)]


@pytest.mark.anyio
async def test_simulator_constructs_only_an_in_memory_sqlite_database(monkeypatch) -> None:
    original = simulator.create_async_engine
    requested_urls: list[str] = []

    def capture_url(database_url: str):
        requested_urls.append(database_url)
        return original(database_url)

    monkeypatch.setattr(simulator, "create_async_engine", capture_url)
    await simulate_battle(SYNTHETIC_SCENARIOS["low-vs-basic"], seed=37)

    assert requested_urls == ["sqlite+aiosqlite://"]


@pytest.mark.anyio
async def test_each_of_the_thirteen_documented_synthetic_scenarios_executes() -> None:
    for scenario in SYNTHETIC_SCENARIOS.values():
        result = await simulate_battle(scenario, seed=23)
        assert result["scenario_id"] == scenario.scenario_id
        assert result["result"] in {"victory", "defeat", "draw", "turn_limit"}
        assert result["participants"]


@pytest.mark.anyio
async def test_scenario_round_trip_replay_and_json_csv_exports() -> None:
    scenario = SYNTHETIC_SCENARIOS["low-vs-basic"]
    assert scenario_from_dict(scenario_to_dict(scenario)) == scenario
    original = await simulate_battle(scenario, seed=5)
    replayed = await replay_battle(original)
    assert export_json(original) == export_json(replayed)
    batch = {
        "results": [
            {
                "scenario_id": "low-vs-basic",
                "seed": 1,
                "simulator_version": "1.0.0",
                "rules_version": "h4-authoritative+h7-combat-rules",
                "party_strategy": "effective_damage",
                "enemy_strategy": "baseline",
                "result": "victory",
                "turns": 3,
                "logical_duration_rounds": 2,
                "actions_executed": 4,
                "total_damage_raw": 8,
                "total_damage_effective": 6,
                "total_damage_received_effective": 2,
                "total_healing_effective": 0,
                "total_healing_wasted": 0,
                "total_mana_consumed": 0,
            }
        ]
    }
    json_report = export_json(batch)
    csv_report = export_csv(batch)

    assert '"scenario_id"' in json_report
    rows = list(csv.DictReader(io.StringIO(csv_report)))
    assert rows[0]["result"] == "victory"
    assert rows[0]["total_damage_effective"] == "6"


def test_aggregate_reports_variability_and_sample_warning() -> None:
    report = aggregate_results(
        [
            {"result": "victory", "turns": 2, "logical_duration_rounds": 1,
             "actions_executed": 2, "total_damage_effective": 8,
             "total_healing_effective": 0, "total_mana_consumed": 2},
            {"result": "defeat", "turns": 4, "logical_duration_rounds": 2,
             "actions_executed": 5, "total_damage_effective": 4,
             "total_healing_effective": 0, "total_mana_consumed": 0},
        ]
    )

    assert report["sample_size"] == 2
    assert report["sample_sufficient_for_exploratory_comparison"] is False
    assert report["win_rate"] == 0.5
    assert report["turns"]["mean"] == 3
    assert report["turns"]["median"] == 3
    assert report["turns"]["population_stddev"] == 1


@pytest.mark.anyio
async def test_work_limits_reject_unbounded_simulation_batches() -> None:
    scenario = BattleScenario(
        "max-work",
        "Too large",
        (
            CombatantSpec("Hero", "player", 1, 20, 0, 1),
            CombatantSpec("Hero2", "player", 1, 20, 0, 1),
            CombatantSpec("Hero3", "player", 1, 20, 0, 1),
            CombatantSpec("Foe", "enemy", 1, 20, 0, 1),
            CombatantSpec("Foe2", "enemy", 1, 20, 0, 1),
            CombatantSpec("Foe3", "enemy", 1, 20, 0, 1),
            CombatantSpec("Foe4", "enemy", 1, 20, 0, 1),
            CombatantSpec("Foe5", "enemy", 1, 20, 0, 1),
            CombatantSpec("Foe6", "enemy", 1, 20, 0, 1),
            CombatantSpec("Foe7", "enemy", 1, 20, 0, 1),
            CombatantSpec("Foe8", "enemy", 1, 20, 0, 1),
            CombatantSpec("Foe9", "enemy", 1, 20, 0, 1),
            CombatantSpec("Foe10", "enemy", 1, 20, 0, 1),
            CombatantSpec("Foe11", "enemy", 1, 20, 0, 1),
        ),
        max_turns=10_000,
    )
    with pytest.raises(ValueError, match="work limit"):
        await run_batch(scenario, range(10_000))
