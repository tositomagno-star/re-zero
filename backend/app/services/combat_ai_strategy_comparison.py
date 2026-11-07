from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
from pathlib import Path
import statistics
from typing import Any

from app.services.combat_balance_analysis import wilson_interval
from app.services.combat_simulator import (
    RULES_VERSION,
    SIMULATOR_VERSION,
    SYNTHETIC_SCENARIOS,
    BattleScenario,
    CombatantSpec,
    SkillSpec,
    run_batch,
    scenario_to_dict,
)

POLICY_VERSION = "h14-experimental-ai-v1"
OUTCOME_PERSPECTIVE = "party/player group victory against the enemy AI"
STRATEGIES = (
    "baseline",
    "aggressive",
    "conservative",
    "economic",
    "tactical",
    "adaptive",
)
STRATEGY_DESCRIPTIONS = {
    "baseline": "H.4 baseline atual; permanece a referência e o padrão oficial.",
    "aggressive": "Prioriza eliminação e dano efetivo; não altera a resolução.",
    "conservative": "Prioriza eliminar alvos de maior ameaça (ataque + magia + velocidade), depois custo e dano.",
    "economic": "Minimiza custo de mana antes de dano e eliminação.",
    "tactical": "Prioriza fraqueza elemental, novo efeito aplicável, eliminação e dano.",
    "adaptive": "Com mana acima de 25% do máximo usa prioridade tática; abaixo disso usa prioridade econômica.",
}
SEEDS = (140, 141, 142, 143, 144)
SCENARIO_IDS = (
    "low-vs-basic",
    "player-vs-group",
    "party-vs-boss",
    "defense-and-healing",
)


def build_experimental_scenarios() -> tuple[BattleScenario, ...]:
    elemental = BattleScenario(
        "h14-elemental-threat",
        "H.14: fraqueza elemental e ameaça a grupo",
        (
            CombatantSpec(
                "Alvo vulnerável",
                "player",
                8,
                240,
                0,
                4,
                magic_attack=6,
                defense=4,
                speed=3,
                weaknesses=("fire",),
            ),
            CombatantSpec(
                "Alvo resistente",
                "player",
                8,
                240,
                0,
                20,
                magic_attack=10,
                defense=7,
                speed=8,
            ),
            CombatantSpec(
                "Mago inimigo",
                "enemy",
                8,
                320,
                30,
                4,
                magic_attack=12,
                speed=9,
                skills=(
                    SkillSpec("Chama fraca", "magic", 4, 5, "fire"),
                    SkillSpec("Orbe forte", "magic", 14, 5, "arcane"),
                ),
            ),
        ),
        max_turns=30,
    )
    mana = BattleScenario(
        "h14-mana-budget",
        "H.14: decisão sob orçamento de mana",
        (
            CombatantSpec("Alvo durável A", "player", 9, 350, 0, 3, speed=4),
            CombatantSpec("Alvo durável B", "player", 9, 350, 0, 3, speed=3),
            CombatantSpec(
                "Feiticeiro econômico",
                "enemy",
                9,
                400,
                18,
                4,
                magic_attack=10,
                speed=8,
                skills=(
                    SkillSpec("Rajada custosa", "magic", 15, 8, "arcane"),
                    SkillSpec("Raio econômico", "magic", 7, 2, "arcane"),
                ),
            ),
        ),
        max_turns=30,
    )
    effects = BattleScenario(
        "h14-effect-priority",
        "H.14: aplicação de efeito e alvo já afetado",
        (
            CombatantSpec("Defensor A", "player", 9, 300, 0, 3, defense=4, speed=4),
            CombatantSpec("Defensor B", "player", 9, 300, 0, 3, defense=4, speed=3),
            CombatantSpec(
                "Invocador inimigo",
                "enemy",
                9,
                400,
                24,
                4,
                magic_attack=10,
                speed=8,
                skills=(
                    SkillSpec(
                        "Toxina persistente",
                        "special",
                        3,
                        4,
                        "poison",
                        additional_effects={
                            "effect_type": "damage_over_time",
                            "damage_per_turn": 4,
                            "duration": 3,
                        },
                    ),
                    SkillSpec("Pulso arcano", "magic", 12, 4, "arcane"),
                ),
            ),
        ),
        max_turns=30,
    )
    return (
        *(SYNTHETIC_SCENARIOS[scenario_id] for scenario_id in SCENARIO_IDS),
        elemental,
        mana,
        effects,
    )


def _party_data(battle: dict[str, Any]) -> dict[str, Any]:
    party = [
        participant
        for participant in battle["participants"]
        if participant["side"] == "player"
    ]
    initial_hp = sum(participant["hp_initial"] for participant in party)
    remaining_hp = sum(participant["hp_final"] for participant in party)
    initial_mana = sum(participant["mana_initial"] for participant in party)
    remaining_mana = sum(participant["mana_remaining"] for participant in party)
    skill_sides: dict[str, set[str]] = {}
    for participant in battle["scenario"]["participants"]:
        for skill in participant.get("skills", []):
            skill_sides.setdefault(str(skill["name"]), set()).add(
                str(participant["side"])
            )
    all_skill_metrics = battle["skills"]
    party_skill_metrics = {
        name: metric
        for name, metric in all_skill_metrics.items()
        if "player" in skill_sides.get(name, set())
    }
    enemy_skill_metrics = {
        name: metric
        for name, metric in all_skill_metrics.items()
        if "enemy" in skill_sides.get(name, set())
    }

    def skill_totals(metrics: dict[str, Any]) -> dict[str, Any]:
        uses = sum(int(metric["uses"]) for metric in metrics.values())
        mana = sum(int(metric["mana_cost"]) for metric in metrics.values())
        damage = sum(int(metric["effective_damage"]) for metric in metrics.values())
        healing = sum(int(metric["healing"]) for metric in metrics.values())
        return {
            "metrics": metrics,
            "uses": uses,
            "mana": mana,
            "effective_damage": damage,
            "healing": healing,
            "damage_per_mana": damage / mana if mana else None,
            "effects": sum(
                int(metric.get("effect_application_count", 0))
                for metric in metrics.values()
            ),
        }

    party_skills = skill_totals(party_skill_metrics)
    enemy_skills = skill_totals(enemy_skill_metrics)
    enemies = [
        participant
        for participant in battle["participants"]
        if participant["side"] == "enemy"
    ]
    enemy_initial_mana = sum(participant["mana_initial"] for participant in enemies)
    enemy_remaining_mana = sum(
        participant["mana_remaining"] for participant in enemies
    )
    enemy_initial_hp = sum(participant["hp_initial"] for participant in enemies)
    enemy_remaining_hp = sum(participant["hp_final"] for participant in enemies)
    target_selections = battle.get("target_selections", {}).get("player", {})
    player_actions = sum(target_selections.values())
    target_focus_share = (
        max(target_selections.values()) / player_actions if player_actions else None
    )
    return {
        "party_size": len(party),
        "party_survivors": sum(bool(item["survived"]) for item in party),
        "party_defeated": sum(not bool(item["survived"]) for item in party),
        "party_survival_rate": (
            sum(bool(item["survived"]) for item in party) / len(party) if party else None
        ),
        "hp_initial": initial_hp,
        "hp_remaining": remaining_hp,
        "hp_remaining_fraction": remaining_hp / initial_hp if initial_hp else None,
        "mana_initial": initial_mana,
        "mana_remaining": remaining_mana,
        "mana_consumed": initial_mana - remaining_mana,
        "party_damage_raw": sum(int(item["damage_raw"]) for item in party),
        "party_damage_effective": sum(int(item["damage_effective"]) for item in party),
        "party_damage_received_raw": sum(
            int(item["damage_received_raw"]) for item in party
        ),
        "party_damage_received_effective": sum(
            int(item["damage_received_effective"]) for item in party
        ),
        "skill_uses": party_skills["uses"],
        "skill_mana_consumed": party_skills["mana"],
        "skill_effective_damage": party_skills["effective_damage"],
        "skill_damage_per_mana": party_skills["damage_per_mana"],
        "enemy_hp_initial": enemy_initial_hp,
        "enemy_hp_remaining": enemy_remaining_hp,
        "enemies_defeated": battle.get("enemies_defeated", 0),
        "enemy_damage_dealt_raw": sum(
            int(item["damage_received_raw"]) for item in party
        ),
        "enemy_damage_dealt_effective": sum(
            int(item["damage_received_effective"]) for item in party
        ),
        "enemy_damage_received_effective": sum(
            int(item["damage_received_effective"]) for item in enemies
        ),
        "enemy_mana_initial": enemy_initial_mana,
        "enemy_mana_remaining": enemy_remaining_mana,
        "enemy_mana_consumed": enemy_initial_mana - enemy_remaining_mana,
        "enemy_skill_uses": enemy_skills["uses"],
        "enemy_skill_mana_consumed": enemy_skills["mana"],
        "enemy_skill_effective_damage": enemy_skills["effective_damage"],
        "enemy_skill_damage_per_mana": enemy_skills["damage_per_mana"],
        "enemy_skill_healing": enemy_skills["healing"],
        "enemy_effects_applied": enemy_skills["effects"],
        "healing_effective": sum(int(item["healing_effective"]) for item in party),
        "skill_healing_effective": party_skills["healing"],
        "effects_applied": party_skills["effects"],
        "skill_metrics": party_skill_metrics,
        "enemy_skill_metrics": enemy_skill_metrics,
        "players_defeated": battle.get("players_defeated", 0),
        "target_selections_by_party": target_selections,
        "party_target_focus_share": target_focus_share,
        "enemy_target_selections": battle.get("target_selections", {}).get("enemy", {}),
        "enemy_target_focus_share": battle.get("target_focus_share", {}).get("enemy"),
        "enemy_action_selections": battle.get("action_selections", {}).get("enemy", {}),
        "no_action_turns": battle.get("no_action_turns", 0),
        "invalid_action_count": None,
    }


def _strategy_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    outcome_counts = {
        name: sum(battle["result"] == name for battle in results)
        for name in ("victory", "defeat", "draw", "turn_limit")
    }
    wins = outcome_counts["victory"]
    confidence_interval = (
        wilson_interval(wins, len(results)) if results else None
    )
    metrics = [_party_data(battle) for battle in results]

    def mean(field: str) -> float | None:
        values = [item[field] for item in metrics if item[field] is not None]
        return statistics.fmean(values) if values else None

    target_counts: dict[str, int] = {}
    enemy_action_counts: dict[str, int] = {}
    party_skill_totals: dict[str, dict[str, int]] = {}
    enemy_skill_totals: dict[str, dict[str, int]] = {}

    def accumulate_skill_metrics(
        totals: dict[str, dict[str, Any]], source: dict[str, Any]
    ) -> None:
        for skill_name, skill in source.items():
            total = totals.setdefault(
                skill_name,
                {
                    "uses": 0,
                    "effective_damage": 0,
                    "healing": 0,
                    "mana_cost": 0,
                    "effect_application_count": 0,
                },
            )
            for key in total:
                total[key] += int(skill.get(key, 0))

    for data in metrics:
        for target, count in data["enemy_target_selections"].items():
            target_counts[target] = target_counts.get(target, 0) + count
        for action, count in data["enemy_action_selections"].items():
            enemy_action_counts[action] = enemy_action_counts.get(action, 0) + count
        accumulate_skill_metrics(party_skill_totals, data["skill_metrics"])
        accumulate_skill_metrics(enemy_skill_totals, data["enemy_skill_metrics"])
    for totals in (party_skill_totals, enemy_skill_totals):
        for skill in totals.values():
            skill["damage_per_mana"] = (
                skill["effective_damage"] / skill["mana_cost"]
                if skill["mana_cost"]
                else None
            )
            skill["healing_per_mana"] = (
                skill["healing"] / skill["mana_cost"]
                if skill["mana_cost"]
                else None
            )
    return {
        "sample_size": len(results),
        "outcome_counts": outcome_counts,
        "win_rate": wins / len(results) if results else None,
        "win_rate_wilson_95_nominal": (
            list(confidence_interval) if confidence_interval is not None else None
        ),
        "confidence_interval_interpretation": (
            "Nominal descriptive Wilson interval only; seeds do not create independent "
            "random trials in this deterministic combat engine."
        ),
        "mean_party_survival_rate": mean("party_survival_rate"),
        "mean_hp_remaining": mean("hp_remaining"),
        "mean_hp_remaining_fraction": mean("hp_remaining_fraction"),
        "mean_party_damage_raw": mean("party_damage_raw"),
        "mean_party_damage_effective": mean("party_damage_effective"),
        "mean_party_damage_received_raw": mean("party_damage_received_raw"),
        "mean_party_damage_received_effective": mean(
            "party_damage_received_effective"
        ),
        "mean_mana_consumed": mean("mana_consumed"),
        "mean_mana_remaining": mean("mana_remaining"),
        "mean_skill_uses": mean("skill_uses"),
        "mean_skill_damage_per_mana": mean("skill_damage_per_mana"),
        "mean_enemy_damage_dealt_effective": mean("enemy_damage_dealt_effective"),
        "mean_enemy_damage_received_effective": mean(
            "enemy_damage_received_effective"
        ),
        "mean_enemy_mana_consumed": mean("enemy_mana_consumed"),
        "mean_enemy_mana_remaining": mean("enemy_mana_remaining"),
        "mean_enemy_skill_uses": mean("enemy_skill_uses"),
        "mean_enemy_skill_mana_consumed": mean("enemy_skill_mana_consumed"),
        "mean_enemy_skill_damage_per_mana": mean(
            "enemy_skill_damage_per_mana"
        ),
        "mean_enemy_skill_healing": mean("enemy_skill_healing"),
        "mean_enemy_effects_applied": mean("enemy_effects_applied"),
        "mean_healing_effective": mean("healing_effective"),
        "mean_skill_healing_effective": mean("skill_healing_effective"),
        "mean_effects_applied": mean("effects_applied"),
        "mean_logical_duration_rounds": (
            statistics.fmean(int(battle["logical_duration_rounds"]) for battle in results)
            if results
            else None
        ),
        "mean_players_defeated": mean("players_defeated"),
        "mean_enemies_defeated": mean("enemies_defeated"),
        "mean_enemy_target_focus_share": mean("enemy_target_focus_share"),
        "mean_party_target_focus_share": mean("party_target_focus_share"),
        "enemy_target_selections": target_counts,
        "enemy_action_selections": enemy_action_counts,
        "total_no_action_turns": sum(
            int(item["no_action_turns"]) for item in metrics
        ),
        "invalid_action_count": (
            None
            if any(item["invalid_action_count"] is None for item in metrics)
            else sum(int(item["invalid_action_count"]) for item in metrics)
        ),
        "skill_metrics": party_skill_totals,
        "enemy_skill_usage": enemy_skill_totals,
    }


async def run_ai_strategy_comparison(
    *,
    scenarios: tuple[BattleScenario, ...] | None = None,
    seeds: tuple[int, ...] = SEEDS,
) -> dict[str, Any]:
    selected_scenarios = scenarios or build_experimental_scenarios()
    scenario_reports: list[dict[str, Any]] = []
    all_battles: list[dict[str, Any]] = []
    all_failures: list[dict[str, Any]] = []
    for scenario in selected_scenarios:
        strategy_reports = {}
        for strategy in STRATEGIES:
            batch = await run_batch(
                scenario,
                seeds,
                party_strategy="effective_damage",
                enemy_strategy=strategy,
            )
            failures = [
                {
                    "scenario_id": scenario.scenario_id,
                    "strategy": strategy,
                    **failure,
                }
                for failure in batch["failures"]
            ]
            all_failures.extend(failures)
            for battle in batch["results"]:
                battle["policy_version"] = POLICY_VERSION
                battle["policy_strategy"] = strategy
                battle["party_strategy"] = "effective_damage"
                battle["scenario_parameters"] = scenario_to_dict(scenario)
                all_battles.append(battle)
            strategy_reports[strategy] = {
                "aggregate": _strategy_summary(batch["results"]),
                "results": batch["results"],
                "failures": failures,
            }
        scenario_reports.append(
            {
                "scenario_id": scenario.scenario_id,
                "scenario_name": scenario.name,
                "scenario": scenario_to_dict(scenario),
                "party_size": sum(
                    item.side == "player" for item in scenario.participants
                ),
                "enemy_size": sum(
                    item.side == "enemy" for item in scenario.participants
                ),
                "seed_set": list(seeds),
                "strategies": strategy_reports,
                "paired_vs_baseline": _paired_comparisons(strategy_reports, seeds),
            }
        )
    return {
        "stage": "H.14",
        "source": "synthetic-only",
        "canonical_ai_replaced": False,
        "policy_version": POLICY_VERSION,
        "outcome_perspective": OUTCOME_PERSPECTIVE,
        "simulator_version": SIMULATOR_VERSION,
        "rules_version": RULES_VERSION,
        "strategies": list(STRATEGIES),
        "strategy_descriptions": STRATEGY_DESCRIPTIONS,
        "seeds": list(seeds),
        "scenario_count": len(selected_scenarios),
        "battle_count": len(all_battles),
        "simulation_failure_count": len(all_failures),
        "simulation_failures": all_failures,
        "scenarios": scenario_reports,
        "battles": all_battles,
        "limitations": [
            "A IA oficial permanece baseline; as estratégias H.14 são escolhas explícitas do simulador.",
            "O motor atual não oferece ação defensiva explícita, então 'conservative' conserva mana e prioriza ameaças, sem criar defesa.",
            "Os seeds pareados são reproduzíveis, mas o motor não usa RNG; repetir seeds não gera ensaios independentes.",
            "O intervalo de Wilson é apresentado somente como referência nominal descritiva e não como inferência válida para estes seeds determinísticos.",
            "O motor registra ações resolvidas, mas não registra tentativas inválidas rejeitadas; falhas de simulação são reportadas separadamente.",
            "Os agregados de habilidades H.11 são agrupados por nome de exibição; nomes iguais entre os lados podem ser combinados e não ocorreram nos cenários H.14.",
            "Dano contínuo fica contabilizado como dano recebido pelo grupo alvo, mas não pode ser atribuído ao autor original pelas métricas de participante do motor.",
            "Ações em área, cooperação coordenada, controle de condições avançado e inteligência de grupo não fazem parte do contrato atual do motor.",
        ],
        "conclusions": {
            "synthetic_observations": _observed_synthetic_findings(scenario_reports),
            "hypotheses": [
                "Políticas econômicas podem preservar mana enquanto prolongam a exposição ao dano.",
                "A prioridade de ameaça da política conservadora pode ser útil contra composições com inimigos de alto ataque.",
                "A política adaptativa pode combinar eficiência de alvo e custo quando há restrição de mana.",
            ],
            "statistical_limitations": (
                "A amostra por cenário é pequena e determinística; não se declara superioridade "
                "nem significância estatística. Pares descrevem diferenças observadas, não "
                "estimativas populacionais."
            ),
        },
    }


def _paired_comparisons(
    strategies: dict[str, Any],
    seeds: tuple[int, ...],
) -> dict[str, Any]:
    baseline = {
        int(result["seed"]): result
        for result in strategies["baseline"]["results"]
    }
    comparisons: dict[str, Any] = {}
    for name in STRATEGIES:
        if name == "baseline":
            continue
        by_seed = {
            int(result["seed"]): result for result in strategies[name]["results"]
        }
        pairs = []
        for seed in seeds:
            if seed not in baseline or seed not in by_seed:
                continue
            base = baseline[seed]
            candidate = by_seed[seed]
            pairs.append(
                {
                    "seed": seed,
                    "baseline_result": base["result"],
                    "strategy_result": candidate["result"],
                    "result_changed": base["result"] != candidate["result"],
                    "baseline_rounds": base["logical_duration_rounds"],
                    "strategy_rounds": candidate["logical_duration_rounds"],
                    "round_delta": (
                        int(candidate["logical_duration_rounds"])
                        - int(base["logical_duration_rounds"])
                    ),
                    "baseline_party_damage": _party_data(base)[
                        "party_damage_effective"
                    ],
                    "strategy_party_damage": _party_data(candidate)[
                        "party_damage_effective"
                    ],
                    "baseline_party_survival": _party_data(base)[
                        "party_survival_rate"
                    ],
                    "strategy_party_survival": _party_data(candidate)[
                        "party_survival_rate"
                    ],
                }
            )
        comparisons[name] = {
            "pair_count": len(pairs),
            "same_outcome_pairs": sum(
                not item["result_changed"] for item in pairs
            ),
            "strategy_won_outcome_pairs": sum(
                item["strategy_result"] == "victory"
                and item["baseline_result"] != "victory"
                for item in pairs
            ),
            "strategy_lost_outcome_pairs": sum(
                item["baseline_result"] == "victory"
                and item["strategy_result"] != "victory"
                for item in pairs
            ),
            "mean_round_delta": (
                statistics.fmean(item["round_delta"] for item in pairs)
                if pairs
                else None
            ),
            "pairs": pairs,
            "inferential_test": None,
        }
    return comparisons


def _observed_synthetic_findings(
    scenarios: list[dict[str, Any]],
) -> list[str]:
    comparisons = [
        comparison
        for scenario in scenarios
        for comparison in scenario["paired_vs_baseline"].values()
    ]
    pair_count = sum(item["pair_count"] for item in comparisons)
    changed_outcomes = sum(
        pair["result_changed"]
        for comparison in comparisons
        for pair in comparison["pairs"]
    )
    findings = [
        (
            f"Em {pair_count} pares de estratégia contra baseline, "
            f"{changed_outcomes} tiveram resultado de batalha diferente; "
            "os seeds repetem execuções determinísticas e não são amostras independentes."
        )
    ]
    by_id = {scenario["scenario_id"]: scenario for scenario in scenarios}
    effect_case = by_id.get("h14-effect-priority")
    if effect_case is not None:
        baseline = effect_case["strategies"]["baseline"]["aggregate"]
        tactical = effect_case["strategies"]["tactical"]["aggregate"]
        findings.append(
            "No cenário sintético de efeitos, baseline aplicou em média "
            f"{baseline['mean_enemy_effects_applied']:.1f} efeitos/batalha e "
            f"tactical {tactical['mean_enemy_effects_applied']:.1f}; a comparação "
            "não alterou as regras de dano contínuo."
        )
    mana_case = by_id.get("h14-mana-budget")
    if mana_case is not None:
        baseline = mana_case["strategies"]["baseline"]["aggregate"]
        economic = mana_case["strategies"]["economic"]["aggregate"]
        findings.append(
            "No orçamento sintético de mana, baseline consumiu em média "
            f"{baseline['mean_enemy_mana_consumed']:.1f} mana por batalha e economic "
            f"{economic['mean_enemy_mana_consumed']:.1f}; o resultado de batalha "
            "deve ser lido no contexto e na tabela pareada desse cenário."
        )
    elemental_case = by_id.get("h14-elemental-threat")
    if elemental_case is not None:
        tactical = elemental_case["strategies"]["tactical"]["aggregate"]
        findings.append(
            "No encontro elemental sintético, a contagem de alvos escolhidos pela "
            f"política tática foi {json.dumps(tactical['enemy_target_selections'], ensure_ascii=False)}."
        )
    boss_case = by_id.get("party-vs-boss")
    conservative = boss_case and boss_case["strategies"]["conservative"]["aggregate"]
    baseline_boss = boss_case and boss_case["strategies"]["baseline"]["aggregate"]
    if conservative is not None and baseline_boss is not None:
        findings.append(
            "Contra o boss sintético, conservadora e baseline tiveram "
            f"{conservative['outcome_counts']} e "
            f"{baseline_boss['outcome_counts']} respectivamente; seleção diferente "
            "não melhorou o resultado nesse contexto."
        )
    return findings


def report_to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Etapa H.14 — Comparação de estratégias alternativas da IA",
        "",
        "**Escopo:** cenários sintéticos executados no motor H.4/H.7 por meio do simulador H.11. "
        "A IA oficial continua inalterada.",
        "",
        "## Resumo",
        "",
        f"- Políticas avaliadas: {', '.join(report['strategies'])}.",
        f"- Cenários: **{report['scenario_count']}**; batalhas: **{report['battle_count']}**.",
        f"- A taxa de vitória refere-se ao grupo jogador contra a IA: `{report['outcome_perspective']}`.",
        f"- Seeds pareadas: `{', '.join(map(str, report['seeds']))}`.",
        f"- Versão das políticas: `{report['policy_version']}`.",
        "- Os resultados são separados por cenário, sem misturar tamanhos de grupo ou dificuldades.",
        "",
        "| Política | Regra de seleção experimental |",
        "|---|---|",
        *(
            f"| {name} | {description} |"
            for name, description in report["strategy_descriptions"].items()
        ),
        "",
        "## Resultados por cenário",
        "",
    ]
    for scenario in report["scenarios"]:
        lines.extend(
            [
                f"### {scenario['scenario_name']}",
                "",
                f"Composição: {scenario['party_size']} jogador(es) × "
                f"{scenario['enemy_size']} inimigo(s). Cenário `{scenario['scenario_id']}`.",
                "",
                "| Estratégia IA | Vitórias do grupo | Derrotas | Empates | Limite | Taxa de vitória do grupo | IC Wilson 95% nominal | Sobrevivência grupo | HP grupo restante | Dano grupo | Dano recebido pelo grupo | Mana IA usada/restante | Dano efetivo IA | Mana IA por habilidade | Dano IA/habilidade/mana | Cura grupo | Efeitos IA | Rodadas | Jogadores derrotados | Inimigos derrotados | Foco do alvo IA | Falhas |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for strategy in STRATEGIES:
            summary = scenario["strategies"][strategy]["aggregate"]
            ci = summary["win_rate_wilson_95_nominal"]
            ci_text = (
                f"{ci[0]:.0%}–{ci[1]:.0%}" if ci is not None else "n/d"
            )
            outcomes = summary["outcome_counts"]
            lines.append(
                f"| {strategy} | {outcomes['victory']} | {outcomes['defeat']} | "
                f"{outcomes['draw']} | {outcomes['turn_limit']} | "
                f"{_percent(summary['win_rate'])} | {ci_text} | "
                f"{_percent(summary['mean_party_survival_rate'])} | "
                f"{_number(summary['mean_hp_remaining'])} | "
                f"{_number(summary['mean_party_damage_effective'])} | "
                f"{_number(summary['mean_party_damage_received_effective'])} | "
                f"{_number(summary['mean_enemy_mana_consumed'])}/"
                f"{_number(summary['mean_enemy_mana_remaining'])} | "
                f"{_number(summary['mean_enemy_damage_dealt_effective'])} | "
                f"{_number(summary['mean_enemy_skill_mana_consumed'])} | "
                f"{_number(summary['mean_enemy_skill_damage_per_mana'])} | "
                f"{_number(summary['mean_healing_effective'])} | "
                f"{_number(summary['mean_enemy_effects_applied'])} | "
                f"{_number(summary['mean_logical_duration_rounds'])} | "
                f"{_number(summary['mean_players_defeated'])} | "
                f"{_number(summary['mean_enemies_defeated'])} | "
                f"{_percent(summary['mean_enemy_target_focus_share'])} | "
                f"{len(scenario['strategies'][strategy]['failures'])} |"
            )
        lines.extend(
            [
                "",
                "#### Comparação pareada com baseline",
                "",
                "| Estratégia | Pares | Mesmo resultado | Vitórias adicionadas | Vitórias perdidas | Delta médio de rodadas |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for name, comparison in scenario["paired_vs_baseline"].items():
            lines.append(
                f"| {name} | {comparison['pair_count']} | "
                f"{comparison['same_outcome_pairs']} | "
                f"{comparison['strategy_won_outcome_pairs']} | "
                f"{comparison['strategy_lost_outcome_pairs']} | "
                f"{_number(comparison['mean_round_delta'])} |"
            )
        lines.extend(
            [
                "",
                "#### Seleção de alvos e ações",
                "",
            ]
        )
        for strategy in STRATEGIES:
            summary = scenario["strategies"][strategy]["aggregate"]
            lines.append(
                f"- **{strategy}:** alvos IA `{json.dumps(summary['enemy_target_selections'], ensure_ascii=False)}`; "
                f"ações IA `{json.dumps(summary['enemy_action_selections'], ensure_ascii=False)}`; "
                f"habilidades IA `{json.dumps(summary['enemy_skill_usage'], ensure_ascii=False)}`; "
                f"foco médio `{_percent(summary['mean_enemy_target_focus_share'])}`; "
                f"foco de alvo do grupo `{_percent(summary['mean_party_target_focus_share'])}`; "
                f"turnos sem ação válida `{summary['total_no_action_turns']}`."
            )
        lines.append("")
    lines.extend(
        [
            "## Resultados sintéticos observados",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["conclusions"]["synthetic_observations"])
    lines.extend(["", "## Hipóteses", ""])
    lines.extend(f"- {item}" for item in report["conclusions"]["hypotheses"])
    lines.extend(
        [
            "",
            "## Limitações estatísticas e do motor",
            "",
            report["conclusions"]["statistical_limitations"],
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.extend(
        [
            "",
            "Os intervalos de Wilson são nominais e não devem ser interpretados como "
            "intervalos inferenciais: o motor é determinístico e seeds diferentes só "
            "mudam identificadores. Nenhuma estratégia é declarada superior ou adotada "
            "como política oficial.",
            "",
            "## Estratégias para investigação posterior",
            "",
            "- Repetir a matriz com catálogo canônico somente após autorização explícita de acesso aos dados, fora desta etapa.",
            "- Ampliar cenários sintéticos de grupo para testar ameaça, seleção de alvo e habilidades de cura/efeito.",
            "- Instrumentar rejeições e ações inelegíveis no simulador antes de tirar conclusões sobre falhas de decisão.",
            "- Adicionar uma ação defensiva formal ao motor apenas em etapa própria, com revisão das regras; H.14 não altera o motor.",
            "",
            "## Artefatos",
            "",
            "Dados completos: `etapa-h14-ai-strategy-comparison.json`; métricas por batalha/estratégia: `etapa-h14-ai-strategy-comparison.csv`.",
            "",
        ]
    )
    return "\n".join(lines)


def _percent(value: float | None) -> str:
    return "n/d" if value is None else f"{value:.0%}"


def _number(value: float | int | None) -> str:
    return "n/d" if value is None else f"{value:.2f}"


def report_to_csv(report: dict[str, Any]) -> str:
    stream = io.StringIO(newline="")
    columns = (
        "scenario_id",
        "scenario_name",
        "party_size",
        "enemy_size",
        "strategy",
        "policy_version",
        "seed",
        "result",
        "win",
        "party_size_in_battle",
        "party_survivors",
        "party_defeated",
        "party_survival_rate",
        "hp_initial",
        "hp_remaining",
        "hp_remaining_fraction",
        "party_damage_raw",
        "party_damage_effective",
        "party_damage_received_raw",
        "party_damage_received_effective",
        "mana_consumed",
        "mana_remaining",
        "skill_uses",
        "skill_effective_damage",
        "skill_damage_per_mana",
        "enemy_hp_initial",
        "enemy_hp_remaining",
        "enemy_damage_dealt_raw",
        "enemy_damage_dealt_effective",
        "enemy_damage_received_effective",
        "enemy_mana_consumed",
        "enemy_mana_remaining",
        "enemy_skill_uses",
        "enemy_skill_mana_consumed",
        "enemy_skill_effective_damage",
        "enemy_skill_damage_per_mana",
        "enemy_skill_healing",
        "enemy_effects_applied",
        "healing_effective",
        "skill_healing_effective",
        "effects_applied",
        "logical_duration_rounds",
        "players_defeated",
        "enemy_target_selections",
        "party_target_selections",
        "enemy_target_focus_share",
        "party_target_focus_share",
        "enemy_action_selections",
        "enemy_skill_usage",
        "no_action_turns",
        "invalid_action_count",
        "simulation_failure_count",
    )
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for scenario in report["scenarios"]:
        for strategy in STRATEGIES:
            for battle in scenario["strategies"][strategy]["results"]:
                metrics = _party_data(battle)
                writer.writerow(
                    {
                        "scenario_id": scenario["scenario_id"],
                        "scenario_name": scenario["scenario_name"],
                        "party_size": scenario["party_size"],
                        "enemy_size": scenario["enemy_size"],
                        "strategy": strategy,
                        "policy_version": report["policy_version"],
                        "seed": battle["seed"],
                        "result": battle["result"],
                        "win": battle["result"] == "victory",
                        "party_size_in_battle": metrics["party_size"],
                        "party_survivors": metrics["party_survivors"],
                        "party_defeated": metrics["party_defeated"],
                        "party_survival_rate": metrics["party_survival_rate"],
                        "hp_initial": metrics["hp_initial"],
                        "hp_remaining": metrics["hp_remaining"],
                        "hp_remaining_fraction": metrics["hp_remaining_fraction"],
                        "party_damage_raw": metrics["party_damage_raw"],
                        "party_damage_effective": metrics["party_damage_effective"],
                        "party_damage_received_raw": metrics[
                            "party_damage_received_raw"
                        ],
                        "party_damage_received_effective": metrics[
                            "party_damage_received_effective"
                        ],
                        "mana_consumed": metrics["mana_consumed"],
                        "mana_remaining": metrics["mana_remaining"],
                        "skill_uses": metrics["skill_uses"],
                        "skill_effective_damage": metrics["skill_effective_damage"],
                        "skill_damage_per_mana": metrics["skill_damage_per_mana"],
                        "enemy_hp_initial": metrics["enemy_hp_initial"],
                        "enemy_hp_remaining": metrics["enemy_hp_remaining"],
                        "enemy_damage_dealt_raw": metrics["enemy_damage_dealt_raw"],
                        "enemy_damage_dealt_effective": metrics[
                            "enemy_damage_dealt_effective"
                        ],
                        "enemy_damage_received_effective": metrics[
                            "enemy_damage_received_effective"
                        ],
                        "enemy_mana_consumed": metrics["enemy_mana_consumed"],
                        "enemy_mana_remaining": metrics["enemy_mana_remaining"],
                        "enemy_skill_uses": metrics["enemy_skill_uses"],
                        "enemy_skill_mana_consumed": metrics[
                            "enemy_skill_mana_consumed"
                        ],
                        "enemy_skill_effective_damage": metrics[
                            "enemy_skill_effective_damage"
                        ],
                        "enemy_skill_damage_per_mana": metrics[
                            "enemy_skill_damage_per_mana"
                        ],
                        "enemy_skill_healing": metrics["enemy_skill_healing"],
                        "enemy_effects_applied": metrics["enemy_effects_applied"],
                        "healing_effective": metrics["healing_effective"],
                        "skill_healing_effective": metrics["skill_healing_effective"],
                        "effects_applied": metrics["effects_applied"],
                        "logical_duration_rounds": battle[
                            "logical_duration_rounds"
                        ],
                        "players_defeated": metrics["players_defeated"],
                        "enemy_target_selections": json.dumps(
                            metrics["enemy_target_selections"], ensure_ascii=False
                        ),
                        "party_target_selections": json.dumps(
                            metrics["target_selections_by_party"], ensure_ascii=False
                        ),
                        "enemy_target_focus_share": metrics[
                            "enemy_target_focus_share"
                        ],
                        "party_target_focus_share": metrics[
                            "party_target_focus_share"
                        ],
                        "enemy_action_selections": json.dumps(
                            metrics["enemy_action_selections"], ensure_ascii=False
                        ),
                        "enemy_skill_usage": json.dumps(
                            {
                                name: {
                                    key: value
                                    for key, value in metric.items()
                                    if key != "usage_samples"
                                }
                                for name, metric in metrics[
                                    "enemy_skill_metrics"
                                ].items()
                            },
                            ensure_ascii=False,
                        ),
                        "no_action_turns": metrics["no_action_turns"],
                        "invalid_action_count": "",
                        "simulation_failure_count": len(
                            scenario["strategies"][strategy]["failures"]
                        ),
                    }
                )
    return stream.getvalue()


def write_reports(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "etapa-h14-ai-strategy-comparison.md"
    json_path = output_dir / "etapa-h14-ai-strategy-comparison.json"
    csv_path = output_dir / "etapa-h14-ai-strategy-comparison.csv"
    markdown_path.write_text(report_to_markdown(report), encoding="utf-8")
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    csv_path.write_text(report_to_csv(report), encoding="utf-8", newline="")
    return markdown_path, json_path, csv_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compara políticas experimentais de IA H.14 em cenários sintéticos."
    )
    parser.add_argument("--output-dir", type=Path, default=Path("docs"))
    arguments = parser.parse_args()
    report = asyncio.run(run_ai_strategy_comparison())
    for path in write_reports(report, arguments.output_dir):
        print(path)


if __name__ == "__main__":
    main()
