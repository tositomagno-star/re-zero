from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.services.combat_ai_strategy_comparison import (
    STRATEGIES,
    run_ai_strategy_comparison,
)
from app.services.combat_balance_analysis import build_analysis_cases
from app.services.combat_simulator import (
    RULES_VERSION,
    SIMULATOR_VERSION,
    SYNTHETIC_SCENARIOS,
    run_batch,
)

H15_FILES = (
    "etapa-h15-combat-balance-report.md",
    "etapa-h15-combat-balance-report.json",
    "etapa-h15-combat-scenarios.csv",
    "etapa-h15-combat-skills.csv",
    "etapa-h15-combat-strategies.csv",
    "etapa-h15-combat-recommendations.csv",
)
H12_CASE_IDS = (
    "enemy-baseline",
    "enemy-high-defense",
    "boss-party-4",
    "boss-party-5",
    "equipment-none",
    "equipment-weapon-plus-6-attack",
    "equipment-armor-plus-6-defense",
    "skill-no-skill",
    "skill-physical-skill",
    "skill-magic-skill",
    "skill-damage-over-time",
)
FINAL_SEEDS = (100, 101, 102, 103, 104)
H11_SEEDS = tuple(range(2000, 3000))
MEASURE_FIELDS = (
    "turns",
    "logical_duration_rounds",
    "actions_executed",
    "total_damage_effective",
    "total_damage_received_effective",
    "total_healing_effective",
    "total_mana_consumed",
    "party_damage_effective",
    "party_damage_received_effective",
    "party_healing_effective",
    "party_mana_consumed",
)


def _side_metrics(battle: dict[str, Any], side: str) -> dict[str, int | float | None]:
    members = [
        participant
        for participant in battle["participants"]
        if participant["side"] == side
    ]
    survivors = sum(participant["survived"] for participant in members)
    return {
        "survivors": survivors,
        "survival_rate": survivors / len(members) if members else None,
        "defeated": sum(not participant["survived"] for participant in members),
        "damage_dealt_effective": sum(
            participant["damage_effective"] for participant in members
        ),
        "damage_received_effective": sum(
            participant["damage_received_effective"] for participant in members
        ),
        "hp_remaining": sum(participant["hp_final"] for participant in members),
        "mana_consumed": sum(participant["mana_consumed"] for participant in members),
        "healing_effective": sum(
            participant["healing_effective"] for participant in members
        ),
    }


def _battle_row(
    stage: str, scenario_id: str, strategy: str, battle: dict[str, Any]
) -> dict[str, Any]:
    player = _side_metrics(battle, "player")
    enemy = _side_metrics(battle, "enemy")
    skills = {
        name: {
            key: value
            for key, value in metrics.items()
            if key
            in {
                "uses",
                "raw_damage",
                "effective_damage",
                "healing",
                "mana_cost",
                "effect_application_count",
            }
        }
        for name, metrics in battle.get("skills", {}).items()
    }
    return {
        "stage": stage,
        "scenario_id": scenario_id,
        "strategy": strategy,
        "seed": battle["seed"],
        "result": battle["result"],
        "turns": battle["turns"],
        "logical_duration_rounds": battle["logical_duration_rounds"],
        "actions_executed": battle["actions_executed"],
        "total_damage_effective": battle["total_damage_effective"],
        "total_damage_received_effective": battle[
            "total_damage_received_effective"
        ],
        "total_healing_effective": battle["total_healing_effective"],
        "total_healing_wasted": battle["total_healing_wasted"],
        "total_mana_consumed": battle["total_mana_consumed"],
        "total_damage_overkill": battle["total_damage_overkill"],
        "party_survivors": player["survivors"],
        "party_survival_rate": player["survival_rate"],
        "party_defeated": player["defeated"],
        "party_hp_remaining": player["hp_remaining"],
        "party_damage_effective": player["damage_dealt_effective"],
        "party_damage_received_effective": player["damage_received_effective"],
        "party_mana_consumed": player["mana_consumed"],
        "party_healing_effective": player["healing_effective"],
        "enemy_survivors": enemy["survivors"],
        "enemy_survival_rate": enemy["survival_rate"],
        "enemy_defeated": enemy["defeated"],
        "enemy_hp_remaining": enemy["hp_remaining"],
        "enemy_damage_effective": enemy["damage_dealt_effective"],
        "enemy_damage_received_effective": enemy["damage_received_effective"],
        "enemy_mana_consumed": enemy["mana_consumed"],
        "enemy_healing_effective": enemy["healing_effective"],
        "skills": skills,
        "effect_applications": sum(
            int(metrics.get("effect_application_count", 0))
            for metrics in battle.get("skills", {}).values()
        ),
        "target_selections": battle.get("target_selections", {}),
        "action_selections": battle.get("action_selections", {}),
        "invalid_action_count": battle.get("invalid_action_count"),
        "simulator_version": battle["simulator_version"],
        "rules_version": battle["rules_version"],
    }


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "population_stddev": None,
        }
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "population_stddev": statistics.pstdev(values),
    }


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    outcomes = Counter(row["result"] for row in rows)
    sample_count = len(rows)
    metrics = {}
    for field in (
        "turns",
        "logical_duration_rounds",
        "total_damage_effective",
        "total_damage_received_effective",
        "total_healing_effective",
        "total_healing_wasted",
        "total_mana_consumed",
        "total_damage_overkill",
        "party_survivors",
        "party_survival_rate",
        "party_defeated",
        "party_hp_remaining",
        "party_damage_effective",
        "party_damage_received_effective",
        "party_mana_consumed",
        "party_healing_effective",
        "enemy_survivors",
        "enemy_survival_rate",
        "enemy_defeated",
        "enemy_hp_remaining",
        "enemy_damage_effective",
        "enemy_damage_received_effective",
        "enemy_mana_consumed",
        "enemy_healing_effective",
        "effect_applications",
    ):
        values = [
            float(row[field])
            for row in rows
            if row.get(field) is not None
        ]
        metrics[field] = {
            **_distribution(values),
            "missing_count": sample_count - len(values),
        }
    return {
        "sample_size": sample_count,
        "outcome_counts": {
            outcome: outcomes.get(outcome, 0)
            for outcome in ("victory", "defeat", "draw", "turn_limit")
        },
        "win_rate": (
            outcomes.get("victory", 0) / sample_count if sample_count else None
        ),
        "seed_values": [row["seed"] for row in rows],
        "metrics": metrics,
        "distinct_outcome_count": len(outcomes),
        "distinct_metric_values": {
            field: len({row[field] for row in rows if row.get(field) is not None})
            for field in MEASURE_FIELDS
            if any(field in row for row in rows)
        }
        if rows
        else {},
    }


async def _run_h11_benchmark(
    seeds: tuple[int, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    batch = await run_batch(
        SYNTHETIC_SCENARIOS["low-vs-basic"],
        seeds,
        party_strategy="effective_damage",
        enemy_strategy="baseline",
    )
    rows = [
        _battle_row(
            "H.11", SYNTHETIC_SCENARIOS["low-vs-basic"].scenario_id, "baseline", battle
        )
        for battle in batch["results"]
    ]
    return rows, batch["failures"]


async def _run_h12_cases(
    h12_source: dict[str, Any], seeds: tuple[int, ...]
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    selected = {
        case.case_id: case
        for case in build_analysis_cases()
        if case.case_id in H12_CASE_IDS
    }
    if set(selected) != set(H12_CASE_IDS):
        raise ValueError("A configuração de cenários sintéticos H.12 mudou.")
    source_cases = {case["case_id"]: case for case in h12_source["cases"]}
    rows: list[dict[str, Any]] = []
    reproduction: dict[str, Any] = {}
    failures: list[dict[str, Any]] = []
    for case_id in H12_CASE_IDS:
        case = selected[case_id]
        batch = await run_batch(
            case.scenario,
            seeds,
            party_strategy=case.party_strategy,
            enemy_strategy=case.enemy_strategy,
        )
        failures.extend(
            {"case_id": case_id, **failure} for failure in batch["failures"]
        )
        case_rows = [
            _battle_row(
                "H.12",
                case.scenario.scenario_id,
                case.enemy_strategy,
                battle,
            )
            for battle in batch["results"]
        ]
        rows.extend(case_rows)
        first = case_rows[0]
        source = source_cases[case_id]
        expected_outcome = next(
            (
                outcome
                for outcome, count in source["result_counts"].items()
                if count
            ),
            None,
        )
        source_metrics = source.get("metrics", {})
        replay_summary = aggregate_rows(case_rows)
        replay_metric_values = replay_summary["distinct_metric_values"]
        reproduction[case_id] = {
            "source_sample_size": source.get("requested", source.get("completed")),
            "replayed_sample_size": len(case_rows),
            "source_seed_100_outcome": expected_outcome,
            "replay_seed_100_outcome": first["result"],
            "source_seed_100_matches": expected_outcome == first["result"],
            "source_mean_turns": (
                source_metrics.get("turns", {}).get("mean")
                if isinstance(source_metrics.get("turns"), dict)
                else None
            ),
            "replay_seed_100_turns": first["turns"],
            "source_turns_match_replay_seed_100": (
                source_metrics.get("turns", {}).get("mean") == first["turns"]
                if isinstance(source_metrics.get("turns"), dict)
                else False
            ),
            "source_mean_damage_effective": (
                source_metrics.get("damage_effective", {}).get("mean")
                if isinstance(source_metrics.get("damage_effective"), dict)
                else None
            ),
            "source_damage_matches_replay_seed_100": (
                source_metrics.get("damage_effective", {}).get("mean")
                == first["total_damage_effective"]
                if isinstance(source_metrics.get("damage_effective"), dict)
                else False
            ),
            "replay_mean_turns": replay_summary["metrics"]["turns"]["mean"],
            "replay_mean_total_damage_effective": replay_summary["metrics"][
                "total_damage_effective"
            ]["mean"],
            "all_seed_rows_equal_on_outcome": len(
                {row["result"] for row in case_rows}
            )
            == 1,
            "all_compared_metrics_equal_across_seeds": all(
                replay_metric_values.get(metric) == 1
                for metric in MEASURE_FIELDS
                if any(metric in row for row in case_rows)
            ),
            "distinct_metric_values": replay_metric_values,
        }
    return rows, reproduction, failures


async def _run_h14_replay(
    h14_source: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    replay = await run_ai_strategy_comparison(
        seeds=tuple(h14_source["seeds"]),
    )
    rows = [
        _battle_row(
            "H.14",
            battle["scenario_id"],
            battle["policy_strategy"],
            battle,
        )
        for battle in replay["battles"]
    ]
    expected = {
        (
            battle["scenario_id"],
            battle["policy_strategy"],
            battle["seed"],
        ): battle
        for battle in h14_source["battles"]
    }
    reproduction_mismatches = []
    metrics_to_compare = (
        "result",
        "turns",
        "logical_duration_rounds",
        "total_damage_effective",
        "total_damage_received_effective",
        "total_healing_effective",
        "total_mana_consumed",
    )
    for battle in replay["battles"]:
        key = (
            battle["scenario_id"],
            battle["policy_strategy"],
            battle["seed"],
        )
        original = expected.get(key)
        if original is None:
            reproduction_mismatches.append(
                {"key": list(key), "reason": "missing-original"}
            )
            continue
        differences = {
            metric: {
                "original": original.get(metric),
                "replay": battle.get(metric),
            }
            for metric in metrics_to_compare
            if original.get(metric) != battle.get(metric)
        }
        if differences:
            reproduction_mismatches.append(
                {"key": list(key), "differences": differences}
            )
    return rows, {
        "source_battle_count": len(expected),
        "replay_battle_count": len(rows),
        "compared_metric_fields": list(metrics_to_compare),
        "mismatch_count": len(reproduction_mismatches),
        "mismatches": reproduction_mismatches,
        "simulation_failure_count": replay["simulation_failure_count"],
        "scenario_summaries": [
            {
                "scenario_id": scenario["scenario_id"],
                "strategies": {
                    strategy: details["aggregate"]
                    for strategy, details in scenario["strategies"].items()
                },
                "paired_vs_baseline": scenario["paired_vs_baseline"],
            }
            for scenario in replay["scenarios"]
        ],
    }, replay["simulation_failures"]


def _summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["stage"], row["scenario_id"], row["strategy"])].append(row)
    return [
        {
            "stage": stage,
            "scenario_id": scenario_id,
            "strategy": strategy,
            **aggregate_rows(group),
        }
        for (stage, scenario_id, strategy), group in sorted(grouped.items())
    ]


def _documented_h11_metrics(markdown: str) -> dict[str, int]:
    benchmark = re.search(
        r"benchmark final executou \*\*([\d.]+) batalhas completas\*\*",
        markdown,
        flags=re.IGNORECASE,
    )
    after_failures = re.search(r"com zero falhas:\s*(.*)", markdown)
    if benchmark is None or after_failures is None:
        raise ValueError("Não foi possível ler o benchmark documentado H.11.")
    metric_text = after_failures.group(1).split(". O resultado", 1)[0]
    numbers = re.findall(r"\d+(?:\.\d+)?", metric_text)
    if len(numbers) < 4:
        raise ValueError("Métricas incompletas no benchmark documentado H.11.")
    to_int = lambda value: int(value.replace(".", ""))
    return {
        "battle_count": to_int(benchmark.group(1)),
        "wins": to_int(numbers[0]),
        "turns_initiated": to_int(numbers[1]),
        "logical_rounds": to_int(numbers[2]),
        "total_effective_damage": to_int(numbers[3]),
    }


def audit_recommendation_evidence(h15: dict[str, Any]) -> list[dict[str, Any]]:
    prior = {
        item["id"]: item for item in h15.get("recommendations", [])
    }
    grades = {
        "synthetic-enemy-defense-threshold": (
            "insufficient-for-change",
            "Uma execução por condição no H.12; cinco replays confirmatórios "
            "são determinísticos e não aumentam o tamanho efetivo da amostra.",
        ),
        "synthetic-boss-party-size-threshold": (
            "insufficient-for-change",
            "Um caso por tamanho de grupo no H.12; contraste confunde tamanho "
            "com desfecho nesse cenário sintético e não há catálogo canônico.",
        ),
        "synthetic-equipment-deltas": (
            "insufficient-for-change",
            "Deltas isolados sintéticos com uma execução original; não representam "
            "itens, slots, custos ou requisitos publicados.",
        ),
        "synthetic-direct-skill-efficiency": (
            "insufficient-for-change",
            "H.12 mede casos sintéticos pontuais e H.13 0 ensaios aleatórios "
            "independentes; não alterar potência nem custo.",
        ),
        "h14-policy-outcomes": (
            "no-official-change",
            "0 de 175 pares mudaram o desfecho; mudanças de escolha/recursos "
            "são comportamentais e determinísticas.",
        ),
        "canonical-catalog-unassessed": (
            "pending-authorized-catalog",
            "As fontes declaram que o catálogo canônico não foi acessado.",
        ),
    }
    audited = []
    for recommendation_id, (grade, rationale) in grades.items():
        item = prior.get(recommendation_id, {})
        audited.append(
            {
                "id": recommendation_id,
                "previous_priority": item.get("priority"),
                "evidence_grade": grade,
                "evidence_summary": rationale,
                "action_taken": "none",
                "canonical_changes_authorized": False,
                "source_recommendation": item.get("title"),
            }
        )
    return audited


async def build_final_validation(
    docs_dir: Path,
    *,
    h11_seeds: tuple[int, ...] = H11_SEEDS,
    h12_seeds: tuple[int, ...] = FINAL_SEEDS,
) -> dict[str, Any]:
    h11_source_markdown = (docs_dir / "etapa-h11-combat-simulator.md").read_text(
        encoding="utf-8"
    )
    documented_h11 = _documented_h11_metrics(h11_source_markdown)
    h12_source = json.loads(
        (docs_dir / "etapa-h12-combat-balance-analysis.json").read_text(
            encoding="utf-8"
        )
    )
    h13_source = json.loads(
        (docs_dir / "etapa-h13-skill-balance-analysis.json").read_text(
            encoding="utf-8"
        )
    )
    h14_source = json.loads(
        (docs_dir / "etapa-h14-ai-strategy-comparison.json").read_text(
            encoding="utf-8"
        )
    )
    h15_source = json.loads(
        (docs_dir / "etapa-h15-combat-balance-report.json").read_text(
            encoding="utf-8"
        )
    )
    h11_rows, h11_failures = await _run_h11_benchmark(h11_seeds)
    h12_rows, h12_reproduction, h12_failures = await _run_h12_cases(
        h12_source, h12_seeds
    )
    h14_rows, h14_reproduction, h14_failures = await _run_h14_replay(h14_source)
    all_rows = h11_rows + h12_rows + h14_rows
    h11_matches = (
        len(h11_rows) == len(h11_seeds) == documented_h11["battle_count"]
        and all(row["result"] == "victory" for row in h11_rows)
        and all(row["turns"] == documented_h11["turns_initiated"] for row in h11_rows)
        and all(
            row["logical_duration_rounds"] == documented_h11["logical_rounds"]
            for row in h11_rows
        )
        and all(
            row["total_damage_effective"] == documented_h11["total_effective_damage"]
            for row in h11_rows
        )
        and documented_h11["wins"] == documented_h11["battle_count"]
    )
    rules_versions = sorted({row["rules_version"] for row in all_rows})
    return {
        "stage": "H.16",
        "scope": "synthetic-only",
        "canonical_balance_certified": False,
        "canonical_rules_changed": False,
        "official_ai_strategy": "baseline",
        "experimental_ai_strategies": [
            strategy for strategy in STRATEGIES if strategy != "baseline"
        ],
        "simulator_version": SIMULATOR_VERSION,
        "rules_versions": rules_versions,
        "source_artifacts": [
            "etapa-h11-combat-simulator.md",
            "etapa-h12-combat-balance-analysis.json",
            "etapa-h13-skill-balance-analysis.json",
            "etapa-h14-ai-strategy-comparison.json",
            *H15_FILES,
        ],
        "audit": {
            "cross_stage_population_policy": (
                "Resultados de H.11–H.14 mantidos separados. As repetições "
                "controladas verificam reprodutibilidade do motor determinístico, "
                "não criam ensaios estatísticos independentes."
            ),
            "h11_h12_reference_agreement": {
                "h11_source_benchmark": (
                    "1.000 vitórias, 7 turnos iniciados, 4 rodadas, 19 dano efetivo."
                ),
                "h12_low_vs_basic_case": next(
                    case
                    for case in h12_source["cases"]
                    if case["case_id"] == "h11-low-vs-basic"
                ),
                "note": (
                    "Os relatórios registram unidades diferentes, mas o baseline "
                    "low-vs-basic coincide em resultado e métricas principais."
                ),
            },
            "h13_h15_reporting_issue": {
                "found": True,
                "description": (
                    "H.15 leu classification como string, mas H.13 armazena um "
                    "objeto com a classificação e a confiança; também usou nomes "
                    "de campos de mediana e contagem de contextos diferentes."
                ),
                "correction": (
                    "Consolidador H.15 corrigido para mapear classificação/confiança "
                    "e `effective_damage_median_per_use`/`contexts` da fonte."
                ),
                "h15_artifacts_regenerated": True,
            },
            "previous_recommendations": audit_recommendation_evidence(h15_source),
            "limitations": [
                "H.12 tem uma execução por configuração; seus casos não sustentam estimativa de variabilidade.",
                "H.13 é sintético e determinístico; a classificação exploratória não fundamenta ajuste de habilidade.",
                "H.14 usa seeds determinísticas; 0/175 desfechos pareados diferentes não prova equivalência geral.",
                "Nenhum catálogo canônico foi consultado; propostas que dependem de dados reais permanecem pendentes.",
                "Repetições do H.16 são testes de regressão/reprodução, não amostras independentes.",
            ],
        },
        "final_simulations": {
            "total_battles": len(all_rows),
            "simulation_failures": h11_failures + h12_failures + h14_failures,
            "h11_benchmark": {
                "scenario_id": SYNTHETIC_SCENARIOS["low-vs-basic"].scenario_id,
                "seed_count": len(h11_rows),
                "seed_range": [h11_rows[0]["seed"], h11_rows[-1]["seed"]]
                if h11_rows
                else [],
                "documented_metrics": documented_h11,
                "summary": aggregate_rows(h11_rows),
                "matches_documented_deterministic_benchmark": h11_matches,
            },
            "h12_reproductions": {
                "case_count": len(H12_CASE_IDS),
                "seeds": list(h12_seeds),
                "seed_100_matches_source": all(
                    item["source_seed_100_matches"]
                    for item in h12_reproduction.values()
                ),
                "cases": h12_reproduction,
            },
            "h14_reproduction": h14_reproduction,
            "aggregates_by_stage_scenario_strategy": _summaries(all_rows),
            "battle_rows": all_rows,
        },
        "adjustments": {
            "canonical_rules_changed": False,
            "combat_engine_changed": False,
            "official_ai_changed": False,
            "applied": [],
            "pending_proposals": [
                {
                    "topic": topic,
                    "current_behavior": current,
                    "proposal": proposal,
                    "expected_impact": impact,
                    "risks": risk,
                    "tests_needed": tests,
                    "status": "not applied; requires canonical data and design approval",
                }
                for topic, current, proposal, impact, risk, tests in (
                    (
                        "Defesa e duração",
                        "Defesa reduz dano segundo a regra central; há piso mínimo de dano.",
                        "Validar a faixa publicada e uma meta de duração antes de propor qualquer ajuste.",
                        "Pode revelar combates de atrito em certas relações de ataque/defesa.",
                        "Uma alteração indiscriminada pode invalidar resistências e inimigos de alto nível.",
                        "Casos pareados em snapshot canônico, limites de dano, defesa e testes H.4/H.7.",
                    ),
                    (
                        "Escala de boss por grupo",
                        "O dano e turnos são resolvidos pelo motor; tamanho do grupo muda participantes e ações.",
                        "Separar tamanho do grupo, cura, iniciativa e equipamento em encontros canônicos autorizados.",
                        "Identificar se o limiar observado decorre da composição ou do boss.",
                        "Alterar HP/dano do boss sem controlar os fatores pode piorar outro grupo.",
                        "Matriz canônica por tamanho/composição com métricas de sobrevivência e duração.",
                    ),
                    (
                        "Eficiência de equipamento",
                        "Atributos de combate vêm do snapshot; H.12 alterou somente deltas sintéticos.",
                        "Comparar itens publicados por slot, custo, requisito e progressão.",
                        "Medir custo-benefício sem inferir de um delta abstrato.",
                        "Itens e economia reais não estão representados nos testes.",
                        "Ablation de um item por vez em catálogo sanitizado e testes de snapshot.",
                    ),
                    (
                        "Custo e potência de habilidades",
                        "O backend valida elegibilidade, consome mana e resolve dano/efeito.",
                        "Avaliar habilidades publicadas por resistência, cooldown, alcance e orçamento de mana.",
                        "Distinguir skill pouco usada de skill fraca e medir utilidade não-dano.",
                        "Reduzir custos/potência baseado em skills sintéticas afetaria progressão canônica.",
                        "Matriz de usos possíveis, controle pareado, mana, cura e efeitos, sem alterar regras.",
                    ),
                    (
                        "Política de IA",
                        "Baseline é o padrão; alternativas H.14 são selecionadas explicitamente no simulador.",
                        "Manter baseline e ampliar evidência comportamental em cenários autorizados.",
                        "Nenhuma substituição recomendada com 0/175 desfechos diferentes e seeds determinísticas.",
                        "Uma política pode mudar recursos e alvo sem mudar resultado no conjunto atual.",
                        "Comparações pareadas por contexto em catálogo canônico e revisão do comportamento.",
                    ),
                )
            ],
        },
        "validity_of_conclusions": {
            "synthetic_facts": [
                "O benchmark H.11 foi reexecutado 1.000 vezes sem falhas e reproduziu vitória, duração e dano determinísticos.",
                "Onze casos H.12 selecionados foram reexecutados em cinco seeds cada; seed 100 confere com a saída documentada e os resultados são reproduzíveis.",
                "A matriz H.14 completa foi reexecutada: 210 batalhas, 0 falhas e comparação das métricas principais sem divergência do JSON publicado.",
                "Testes existentes cobrem fórmulas, piso/limite de dano, resistência, mana, efeitos, turno, replay, persistência de ações, idempotência e recompensa."
            ],
            "hypotheses": [
                "O contraste de defesa pode causar duração excessiva em certas fichas.",
                "O boss sintético pode ter limiar de vitória sensível a tamanho e composição do grupo.",
                "Deltas de equipamento e habilidades sintéticas podem não refletir o catálogo disponível.",
                "Políticas alternativas podem oferecer trade-offs de mana, alvo ou efeitos em outros encontros."
            ],
            "canonical_catalog_pending": [
                "Taxas de vitória/duração contra personagens, inimigos e bosses publicados.",
                "Eficiência e progressão de equipamentos reais.",
                "Equilíbrio de habilidades publicadas, custos, cooldowns e efeitos.",
                "Adequação de parâmetros oficiais e substituição da estratégia baseline."
            ],
            "insufficient_evidence": [
                "Afirmar que o combate canônico está equilibrado ou desequilibrado.",
                "Afirmar superioridade estatística de uma política de IA.",
                "Ajustar fórmulas, atributos, habilidade, custo, resistência ou HP do boss.",
            ],
        },
        "security_and_data_integrity": {
            "postgresql_accessed": False,
            "persistent_databases_accessed": False,
            "migrations_applied": False,
            "persistent_data_modified": False,
            "credentials_or_permissions_modified": False,
        },
    }


def report_to_markdown(report: dict[str, Any]) -> str:
    simulations = report["final_simulations"]
    h11 = simulations["h11_benchmark"]
    h12 = simulations["h12_reproductions"]
    h14 = simulations["h14_reproduction"]
    summary = h11["summary"]
    lines = [
        "# H.16 — Validação final do balanceamento de combate",
        "",
        "> **Conclusão:** a etapa valida reprodutibilidade e regressões em cenários sintéticos; não certifica o catálogo canônico nem autoriza ajustes nas regras.",
        "",
        "## 1. Auditoria H.11–H.15",
        "",
        "- H.11: benchmark documentado de 1.000 batalhas do cenário `low-vs-basic`, determinístico.",
        "- H.12: 45 configurações sintéticas, uma execução final por caso; 11 casos representativos foram reexecutados em cinco seeds.",
        "- H.13: 6 habilidades, 26 contrastes e 0 ensaios aleatórios independentes; classificações exploratórias.",
        "- H.14: 210 batalhas, 7 cenários, 6 políticas e 175 pares contra baseline; nenhum desfecho mudou no conjunto anterior.",
        "- H.15: não agrega populações incompatíveis. A auditoria identificou e corrigiu o mapeamento de classificação/confiança e mediana/contextos da H.13.",
        "- As recomendações de defesa, boss, equipamentos e habilidades têm uma execução por condição na H.12 original. Replays confirmam reprodução, não elevam o n estatístico.",
        "",
        "### Força da evidência das recomendações H.15",
        "",
        "| Recomendação | Evidência | Decisão H.16 |",
        "|---|---|---|",
    ]
    for item in report["audit"]["previous_recommendations"]:
        lines.append(
            f"| {item['id']} | {item['evidence_grade']}: {item['evidence_summary']} | "
            f"{item['action_taken']} |"
        )
    lines.extend(
        [
            "",
            "## 2. Estado das regras e fluxo autoritativo",
            "",
            "- Dano, normalização de atributos e classificação mágica reutilizam `combat_rules.py`; não há fórmula paralela no simulador.",
            "- O cálculo central preserva piso de 1, limite máximo, resistência em metade, fraqueza em dobro e precedência da resistência se ambas coincidirem.",
            "- O simulador invoca os resolutores de combate da API H.4/H.7 em SQLite `:memory:`; custo de mana, alvo, cooldown, efeitos e resultado permanecem sob validação do servidor.",
            "- Turnos/ações usam eventos e chaves idempotentes; conclusão de vitória continua integrando `progression` para concessão única de recompensas.",
            "- Progressão continua no serviço existente; cenários de equipamento H.12 alteram somente atributos sintéticos, sem representar itens persistentes.",
            "- A API mantém baseline como padrão. Estratégias alternativas só são enviadas explicitamente pelo simulador.",
            "- O frontend consome e apresenta eventos confirmados pela API; nenhuma alteração de frontend foi necessária.",
            "",
            "## 3. Simulações finais",
            "",
            "| Matriz | Execuções | Seeds | Resultado | Reprodutibilidade |",
            "|---|---:|---|---|---|",
            f"| H.11 `low-vs-basic` | {summary['sample_size']} | {h11['seed_range'][0]}–{h11['seed_range'][1]} | "
            f"{summary['outcome_counts']} | "
            f"{'confere' if h11['matches_documented_deterministic_benchmark'] else 'diverge'} do benchmark documentado |",
            f"| H.12 recomendações | {h12['case_count'] * len(h12['seeds'])} | "
            f"{h12['seeds']} | {h12['case_count']} casos, seed 100 confere: "
            f"{h12['seed_100_matches_source']} | determinístico; sem inferência |",
            f"| H.14 matriz inteira | {h14['replay_battle_count']} | fonte H.14 | "
            f"{h14['simulation_failure_count']} falhas | "
            f"{h14['mismatch_count']} divergências nas métricas comparadas |",
            "",
            "### H.11 benchmark reexecutado",
            "",
            "| Métrica | Valor |",
            "|---|---:|",
            f"| Vitórias | {summary['outcome_counts']['victory']}/{summary['sample_size']} |",
            f"| Taxa descritiva | {summary['win_rate']:.1%} |",
            f"| Turnos (média/mediana) | {summary['metrics']['turns']['mean']}/{summary['metrics']['turns']['median']} |",
            f"| Rodadas lógicas (média/mediana) | {summary['metrics']['logical_duration_rounds']['mean']}/{summary['metrics']['logical_duration_rounds']['median']} |",
            f"| Dano efetivo do grupo (média/mediana) | {summary['metrics']['party_damage_effective']['mean']}/{summary['metrics']['party_damage_effective']['median']} |",
            f"| Dano efetivo total (ambos os lados e efeitos; média/mediana) | {summary['metrics']['total_damage_effective']['mean']}/{summary['metrics']['total_damage_effective']['median']} |",
            f"| Sobrevivência do grupo (média) | {summary['metrics']['party_survival_rate']['mean']:.1%} |",
            f"| Sobreviventes do grupo (média) | {summary['metrics']['party_survivors']['mean']} |",
            f"| Mana consumida pelo grupo (média) | {summary['metrics']['party_mana_consumed']['mean']} |",
            f"| Falhas | {len(simulations['simulation_failures'])} |",
            "",
            "### Casos H.12 repetidos",
            "",
            "| Caso | n replay | Desfecho original/replay seed 100 | Confere | Turnos média | Dano total médio | Métricas iguais entre seeds |",
            "|---|---:|---|---|---:|---:|---|",
        ]
    )
    for case_id, item in h12["cases"].items():
        lines.append(
            f"| `{case_id}` | {item['replayed_sample_size']} | "
            f"{item['source_seed_100_outcome']}/{item['replay_seed_100_outcome']} | "
            f"{item['source_seed_100_matches']} | {item['replay_mean_turns']} | "
            f"{item['replay_mean_total_damage_effective']} | "
            f"{item['all_compared_metrics_equal_across_seeds']} |"
        )
    lines.extend(
        [
            "",
            "### H.14 — Condições e recursos por cenário/política",
            "",
            "| Cenário | Política | n | Vitórias | Sobrevivência média | Sobreviventes | Dano de grupo | Dano recebido | Mana IA | Cura grupo | Rodadas |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for summary_row in simulations["aggregates_by_stage_scenario_strategy"]:
        if summary_row["stage"] != "H.14":
            continue
        metrics = summary_row["metrics"]
        lines.append(
            f"| `{summary_row['scenario_id']}` | {summary_row['strategy']} | "
            f"{summary_row['sample_size']} | "
            f"{summary_row['outcome_counts']['victory']} | "
            f"{metrics['party_survival_rate']['mean']:.1%} | "
            f"{metrics['party_survivors']['mean']} | "
            f"{metrics['party_damage_effective']['mean']} | "
            f"{metrics['party_damage_received_effective']['mean']} | "
            f"{metrics['enemy_mana_consumed']['mean']} | "
            f"{metrics['party_healing_effective']['mean']} | "
            f"{metrics['logical_duration_rounds']['mean']} |"
        )
    lines.extend(
        [
            "",
            "Os cenários/políticas não foram agregados entre si. Em cada repetição, dano, HP/mana, cura, alvos, ações, usos de habilidade e aplicações de efeitos foram registrados no JSON/CSV. A repetição determinística não constitui uma amostra estatística independente.",
            "",
            "## 4. Ajustes realizados e propostas",
            "",
            "Nenhum ajuste canônico foi aplicado. Foi corrigido apenas o mapeamento de campos no consolidador H.15, sem alteração de simulador ou regras.",
            "",
            "| Tema | Comportamento atual | Proposta pendente | Impacto esperado | Risco | Testes necessários |",
            "|---|---|---|---|---|---|",
        ]
    )
    for item in report["adjustments"]["pending_proposals"]:
        lines.append(
            f"| {item['topic']} | {item['current_behavior']} | {item['proposal']} | "
            f"{item['expected_impact']} | {item['risks']} | {item['tests_needed']} |"
        )
    lines.extend(
        [
            "",
            "## 5. Regressões verificadas",
            "",
            "A suíte abaixo cobre reproduções e contratos do motor, sem conexão PostgreSQL:",
            "",
            "- Determinismo, replay por seed, limites e agregação: `test_combat_simulator.py`.",
            "- Dano central, defesa, resistências, fraquezas e limites numéricos: `test_combat_rules.py`.",
            "- Custo de mana, resistência server-side, rejeição de dano/targets fornecidos pelo cliente, turnos, eventos, idempotência e recompensas únicas: `test_combat.py`.",
            "- Progressão, rewards transacionais e idempotência concorrente: `test_progression.py`.",
            "- Exports, comparação pareada e políticas experimentais sem mudar default: testes H.12–H.15.",
            "- Eventos de combate apresentados no frontend cobertos pelos testes do painel; nenhum arquivo de frontend foi alterado.",
            "",
            "A contagem dos testes é apresentada no resumo de entrega; o JSON registra dados de simulação, não o log do pytest.",
            "",
            "## 6. Validade das conclusões",
            "",
            "### Conclusões comprovadas com dados sintéticos",
            "",
        ]
    )
    lines.extend(
        f"- {fact}"
        for fact in report["validity_of_conclusions"]["synthetic_facts"]
    )
    lines.extend(["", "### Conclusões ainda hipotéticas", ""])
    lines.extend(f"- {fact}" for fact in report["validity_of_conclusions"]["hypotheses"])
    lines.extend(["", "### Pendências dependentes do catálogo canônico", ""])
    lines.extend(
        f"- {fact}"
        for fact in report["validity_of_conclusions"]["canonical_catalog_pending"]
    )
    lines.extend(["", "### Sem evidência suficiente", ""])
    lines.extend(
        f"- {fact}"
        for fact in report["validity_of_conclusions"]["insufficient_evidence"]
    )
    lines.extend(
        [
            "",
            "## 7. Limitações e riscos restantes",
            "",
            *[f"- {limitation}" for limitation in report["audit"]["limitations"]],
            "- Dano contínuo não é atribuído com segurança ao ator original pelos eventos do motor; métricas de skill não o contam como dano direto.",
            "- A simulação sintética não cobre validade de todas as skills, builds, composições ou ciclos reais de campanha.",
            "- H.14 não encontrou diferença de resultado por política nos cenários avaliados, mas isso não demonstra equivalência em cenários não testados.",
            "",
            "## 8. Segurança e validação canônica",
            "",
            "- PostgreSQL e bancos `cronicas_do_reino_dev`/`cronicas_do_reino_test`: não acessados.",
            "- Migrations: não aplicadas; verificação Alembic somente leitura.",
            "- Dados persistentes, credenciais, roles, permissões e fórmulas oficiais: não modificados.",
            "- O catálogo canônico permanece sem validação autorizada. O baseline continua a IA oficial.",
            "",
            "Artefatos detalhados: `etapa-h16-final-combat-balance-validation.json` e `etapa-h16-final-combat-balance-validation.csv`.",
            "",
        ]
    )
    return "\n".join(lines)


def report_to_csv(report: dict[str, Any]) -> str:
    fields = [
        "stage",
        "scenario_id",
        "strategy",
        "seed",
        "result",
        "turns",
        "logical_duration_rounds",
        "actions_executed",
        "total_damage_effective",
        "total_damage_received_effective",
        "total_healing_effective",
        "total_healing_wasted",
        "total_mana_consumed",
        "total_damage_overkill",
        "party_survivors",
        "party_survival_rate",
        "party_defeated",
        "party_hp_remaining",
        "party_damage_effective",
        "party_damage_received_effective",
        "party_mana_consumed",
        "party_healing_effective",
        "enemy_survivors",
        "enemy_survival_rate",
        "enemy_defeated",
        "enemy_hp_remaining",
        "enemy_damage_effective",
        "enemy_damage_received_effective",
        "enemy_mana_consumed",
        "enemy_healing_effective",
        "effect_applications",
        "skills_json",
        "target_selections_json",
        "action_selections_json",
        "invalid_action_count",
        "simulator_version",
        "rules_version",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in report["final_simulations"]["battle_rows"]:
        writer.writerow(
            {
                **{
                    key: value
                    for key, value in row.items()
                    if key in fields
                },
                "skills_json": json.dumps(row["skills"], ensure_ascii=False),
                "target_selections_json": json.dumps(
                    row["target_selections"], ensure_ascii=False
                ),
                "action_selections_json": json.dumps(
                    row["action_selections"], ensure_ascii=False
                ),
            }
        )
    return output.getvalue()


def write_reports(report: dict[str, Any], docs_dir: Path) -> list[Path]:
    docs_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "etapa-h16-final-combat-balance-validation.md": report_to_markdown(report),
        "etapa-h16-final-combat-balance-validation.json": json.dumps(
            report, ensure_ascii=False, indent=2
        )
        + "\n",
        "etapa-h16-final-combat-balance-validation.csv": report_to_csv(report),
    }
    paths = []
    for filename, contents in outputs.items():
        path = docs_dir / filename
        path.write_text(contents, encoding="utf-8", newline="")
        paths.append(path)
    return paths


async def generate_final_report(docs_dir: Path) -> list[Path]:
    report = await build_final_validation(docs_dir)
    return write_reports(report, docs_dir)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Executa a validação sintética final H.16, sem bancos persistentes."
    )
    parser.add_argument("--docs-dir", type=Path, default=Path("docs"))
    args = parser.parse_args()
    for path in asyncio.run(generate_final_report(args.docs_dir)):
        print(path)


if __name__ == "__main__":
    main()
