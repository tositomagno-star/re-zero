import csv
import copy
import json
from pathlib import Path

import pytest

from app.services.combat_balance_consolidation import (
    SOURCE_FILES,
    build_consolidated_report,
    write_reports,
)


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


def _sources():
    return (
        (DOCS / SOURCE_FILES["H.11"]).read_text(encoding="utf-8"),
        json.loads((DOCS / SOURCE_FILES["H.12"]).read_text(encoding="utf-8")),
        json.loads((DOCS / SOURCE_FILES["H.13"]).read_text(encoding="utf-8")),
        json.loads((DOCS / SOURCE_FILES["H.14"]).read_text(encoding="utf-8")),
    )


def test_consolidation_preserves_sources_and_separate_populations() -> None:
    report = build_consolidated_report(*_sources())

    assert report["scope"] == "synthetic-only"
    assert report["canonical_balance_certified"] is False
    assert set(report["sources"]) == {"H.11", "H.12", "H.13", "H.14"}
    assert report["phases"]["H.11"]["battle_count"] == 1000
    assert report["phases"]["H.11"]["reported_population_stddev"] == 0
    assert report["phases"]["H.12"]["scenario_count"] == 45
    assert report["phases"]["H.12"]["battle_count_completed"] == 45
    assert report["phases"]["H.13"]["skill_count"] == 6
    assert report["phases"]["H.13"]["comparison_count"] == 26
    h13_skills = report["phases"]["H.13"]["skills"]
    assert h13_skills[0]["classification"] == "potencialmente forte"
    assert h13_skills[0]["median_effective_damage_per_use"] is not None
    assert h13_skills[0]["battle_contexts"] == 5
    assert report["phases"]["H.14"]["scenario_count"] == 7
    assert report["phases"]["H.14"]["battle_count"] == 210
    assert "Não somar batalhas" in report["population_policy"]
    assert not [
        item for item in report["recommendations"] if item["priority"] == "crítica"
    ]
    assert all(
        {
            "evidence",
            "scenarios",
            "metrics",
            "sample_counts",
            "risk",
            "confidence",
            "next_experiment",
        }
        <= item.keys()
        for item in report["recommendations"]
    )


def test_exports_are_consistent_with_consolidated_json(tmp_path: Path) -> None:
    report = build_consolidated_report(*_sources())
    paths = write_reports(report, tmp_path)
    assert len(paths) == 6

    data = json.loads(
        (tmp_path / "etapa-h15-combat-balance-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert data == report

    with (tmp_path / "etapa-h15-combat-scenarios.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        scenarios = list(csv.DictReader(stream))
    with (tmp_path / "etapa-h15-combat-skills.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        skills = list(csv.DictReader(stream))
    with (tmp_path / "etapa-h15-combat-strategies.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        strategies = list(csv.DictReader(stream))
    with (tmp_path / "etapa-h15-combat-recommendations.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        recommendations = list(csv.DictReader(stream))

    assert len(scenarios) == 45 + 7 * 6
    assert len(skills) == report["phases"]["H.13"]["skill_count"]
    assert len(strategies) == 7 * 6
    assert len(recommendations) == len(report["recommendations"])
    assert all(row["metrics"] for row in recommendations)
    assert all(row["inferential_ci_valid"] == "False" for row in scenarios)

    markdown = (tmp_path / "etapa-h15-combat-balance-report.md").read_text(
        encoding="utf-8"
    )
    assert "## Validade das conclusões" in markdown
    assert all(source["file"] in markdown for source in report["sources"].values())
    assert "não certifica o balanceamento canônico" in markdown


def test_missing_source_metrics_remain_unavailable() -> None:
    h11, h12, h13, h14 = _sources()
    h12 = copy.deepcopy(h12)
    del h12["cases"][0]["metrics"]["damage_effective"]

    report = build_consolidated_report(h11, h12, h13, h14)
    case = report["phases"]["H.12"]["cases"][0]
    assert case["metrics"]["damage_effective"] is None


def test_non_synthetic_source_is_rejected() -> None:
    h11, h12, h13, h14 = _sources()
    h14 = copy.deepcopy(h14)
    h14["source"] = "canonical"

    with pytest.raises(ValueError, match="H.14 não está marcado como sintético"):
        build_consolidated_report(h11, h12, h13, h14)
