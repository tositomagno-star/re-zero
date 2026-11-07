import pytest

from app.services.combat_balance_analysis import (
    _pair_summary,
    build_analysis_cases,
    export_csv,
    export_json,
    export_markdown_summary,
    run_analysis,
    _describe,
    wilson_interval,
)


def test_wilson_interval_matches_known_examples() -> None:
    lower, upper = wilson_interval(5, 10)
    assert lower == pytest.approx(0.2366, abs=0.0001)
    assert upper == pytest.approx(0.7634, abs=0.0001)

    lower_all, upper_all = wilson_interval(10, 10)
    assert lower_all == pytest.approx(0.7225, abs=0.0001)
    assert upper_all == pytest.approx(1)


@pytest.mark.parametrize(
    ("successes", "trials"),
    [(0, 0), (-1, 3), (4, 3)],
)
def test_wilson_interval_rejects_invalid_counts(successes: int, trials: int) -> None:
    with pytest.raises(ValueError):
        wilson_interval(successes, trials)


def test_descriptive_statistics_match_a_small_known_sample() -> None:
    summary = _describe([1, 2, 3, 4])
    assert summary == {
        "count": 4,
        "mean": 2.5,
        "median": 2.5,
        "population_stddev": pytest.approx(1.11803398875),
        "min": 1,
        "max": 4,
        "p25": 1,
        "p50": 2,
        "p75": 3,
        "p90": 4,
    }


def test_analysis_matrix_covers_synthetic_families_and_respects_limits() -> None:
    cases = build_analysis_cases()
    assert len({case.case_id for case in cases}) == len(cases)
    assert {case.family for case in cases} >= {
        "h11-synthetic-scenarios",
        "level-matrix",
        "archetypes",
        "enemy-archetypes",
        "boss-party-scaling",
        "equipment-deltas",
        "skill-comparison",
        "group-compositions",
        "healing-strategy",
    }
    assert all(
        sum(item.side == "player" for item in case.scenario.participants) <= 5
        for case in cases
    )
    assert all(
        case.scenario.scenario_id.startswith("h12-")
        or case.family in {"h11-synthetic-scenarios", "healing-strategy"}
        for case in cases
    )


def test_paired_comparison_uses_only_shared_seed_ids() -> None:
    reference = {
        "case_id": "reference",
        "observations": [
            {"seed": 1, "result": "victory", "turns": 4, "logical_duration_rounds": 2,
             "party_damage_dealt_effective": 10, "party_damage_received_effective": 3,
             "enemy_damage_dealt_effective": 3, "party_healing_effective": 0,
             "total_mana_consumed": 0},
            {"seed": 2, "result": "defeat", "turns": 8, "logical_duration_rounds": 4,
             "party_damage_dealt_effective": 11, "party_damage_received_effective": 9,
             "enemy_damage_dealt_effective": 9, "party_healing_effective": 0,
             "total_mana_consumed": 0},
        ],
    }
    comparison = {
        "case_id": "comparison",
        "observations": [
            {"seed": 2, "result": "victory", "turns": 6, "logical_duration_rounds": 3,
             "party_damage_dealt_effective": 15, "party_damage_received_effective": 4,
             "enemy_damage_dealt_effective": 4, "party_healing_effective": 2,
             "total_mana_consumed": 5},
            {"seed": 3, "result": "victory", "turns": 4, "logical_duration_rounds": 2,
             "party_damage_dealt_effective": 15, "party_damage_received_effective": 4,
             "enemy_damage_dealt_effective": 4, "party_healing_effective": 2,
             "total_mana_consumed": 5},
        ],
    }

    paired = _pair_summary(reference, comparison)
    assert paired["paired_seed_count"] == 1
    assert paired["seeds"] == [2]
    assert paired["mean_paired_win_rate_delta"] == 1
    assert paired["mean_paired_metric_deltas"]["turns"] == -2
    assert paired["inferential_ci"] is None


@pytest.mark.anyio
async def test_small_analysis_is_traceable_and_exports_all_formats() -> None:
    report = await run_analysis([7])
    assert report["synthetic_only"] is True
    assert report["postgres_accessed"] is False
    assert report["seed_count"] == 1
    assert report["scenario_count"] == len(build_analysis_cases())
    assert report["failure_count"] == 0
    assert report["progression_rules"]["max_character_level"] == 10_000
    assert report["paired_comparisons"]
    case_ids = {case["case_id"] for case in report["cases"]}
    findings = report["findings"]
    assert all(set(finding["case_refs"]) <= case_ids for finding in findings)
    assert all(
        finding["scope"] == "synthetic-only"
        for finding in findings
        if finding["severity"].endswith("synthetic-signal")
    )
    canonical = next(
        finding
        for finding in findings
        if finding["finding_id"] == "canonical-content-not-assessed"
    )
    assert canonical["severity"] == "inconclusive"
    assert {
        "synthetic-direct-skill-efficiency",
        "synthetic-level-isolation",
        "synthetic-healing-policy-tradeoff",
    } <= {finding["finding_id"] for finding in findings}
    first = report["cases"][0]
    assert first["scenario"]["scenario_id"] == build_analysis_cases()[0].scenario.scenario_id
    assert first["observations"][0]["seed"] == 7
    assert first["inferential_ci_valid"] is False
    assert "scenario_count" in export_json(report)
    assert "case_id,family,scenario_id,seed" in export_csv(report)
    assert "# H.12" in export_markdown_summary(report)
