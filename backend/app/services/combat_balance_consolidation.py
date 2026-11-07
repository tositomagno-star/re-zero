from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


SOURCE_FILES = {
    "H.11": "etapa-h11-combat-simulator.md",
    "H.12": "etapa-h12-combat-balance-analysis.json",
    "H.13": "etapa-h13-skill-balance-analysis.json",
    "H.14": "etapa-h14-ai-strategy-comparison.json",
}

STRATEGY_METRICS = (
    "sample_size",
    "outcome_counts",
    "win_rate",
    "win_rate_wilson_95_nominal",
    "mean_party_survival_rate",
    "mean_hp_remaining",
    "mean_hp_remaining_fraction",
    "mean_party_damage_effective",
    "mean_party_damage_received_effective",
    "mean_mana_consumed",
    "mean_mana_remaining",
    "mean_enemy_damage_dealt_effective",
    "mean_enemy_mana_consumed",
    "mean_enemy_skill_damage_per_mana",
    "mean_enemy_effects_applied",
    "mean_healing_effective",
    "mean_logical_duration_rounds",
    "mean_players_defeated",
    "mean_enemies_defeated",
    "mean_enemy_target_focus_share",
    "mean_party_target_focus_share",
    "enemy_target_selections",
    "enemy_action_selections",
    "enemy_skill_usage",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _h11_summary(markdown: str) -> dict[str, Any]:
    benchmark = re.search(
        r"benchmark final executou \*\*([\d.]+) batalhas completas\*\*",
        markdown,
        flags=re.IGNORECASE,
    )
    _require(benchmark is not None, "Não foi possível extrair o benchmark H.11.")
    assert benchmark is not None
    after_failure_label = re.search(r"com zero falhas:\s*(.*)", markdown)
    _require(
        after_failure_label is not None,
        "Não foi possível extrair as métricas do benchmark H.11.",
    )
    assert after_failure_label is not None
    metric_text = after_failure_label.group(1).split(". O resultado", 1)[0]
    observed_numbers = re.findall(r"\d+(?:\.\d+)?", metric_text)
    _require(
        len(observed_numbers) >= 4,
        "Métricas incompletas no benchmark H.11.",
    )
    parse_integer = lambda value: int(value.replace(".", ""))
    battle_count = parse_integer(benchmark.group(1))
    wins, turns, rounds, damage = map(parse_integer, observed_numbers[:4])
    deviation = 0 if metric_text.rstrip().endswith("zero") else None
    return {
        "benchmark_scenario": "low-vs-basic",
        "battle_count": int(battle_count),
        "failure_count": 0,
        "wins": int(wins),
        "win_rate": wins / battle_count if battle_count else None,
        "mean_and_median_turns_initiated": turns,
        "mean_logical_rounds": rounds,
        "mean_effective_damage_per_battle": damage,
        "reported_population_stddev": deviation,
        "randomness_note": (
            "Execuções determinísticas; a repetição valida estabilidade do "
            "pipeline, não incerteza estatística."
        ),
    }


def _metric(metrics: dict[str, Any], key: str) -> Any:
    value = metrics.get(key)
    if value is None:
        return None
    return value


def _h12_cases(source: dict[str, Any]) -> list[dict[str, Any]]:
    cases = []
    for case in source["cases"]:
        metrics = case.get("metrics", {})
        party_participants = [
            participant
            for participant in case.get("participant_metrics", [])
            if participant.get("side") == "player"
            and participant.get("survival_rate") is not None
        ]
        cases.append(
            {
                "case_id": case["case_id"],
                "family": case["family"],
                "comparison": case.get("comparison"),
                "sample_size": case.get("requested", case.get("completed")),
                "result_counts": case.get("result_counts", {}),
                "win_rate": case.get("win_rate"),
                "inferential_ci_valid": case.get("inferential_ci_valid", False),
                "metrics": {
                    key: _metric(metrics, key)
                    for key in (
                        "turns",
                        "logical_duration_rounds",
                        "actions_executed",
                        "damage_effective",
                        "healing_effective",
                        "mana_consumed",
                    )
                },
                "side_metrics": case.get("side_metrics", {}),
                "participant_metrics": case.get("participant_metrics", []),
                "party_survival_rate": (
                    sum(item["survival_rate"] for item in party_participants)
                    / len(party_participants)
                    if party_participants
                    else None
                ),
                "observations": case.get("observations", []),
            }
        )
    return cases


def _h13_skills(source: dict[str, Any]) -> list[dict[str, Any]]:
    skills = []
    for skill in source["skills"]:
        metrics = skill["metrics"]
        classification = skill.get("classification", {})
        sample_basis = classification.get("sample_basis", {})
        skills.append(
            {
                "skill": skill["skill"],
                "category": skill.get("category"),
                "skill_type": skill.get("skill_type"),
                "classification": classification.get("classification"),
                "uses": metrics.get("uses"),
                "effective_direct_damage": metrics.get("effective_direct_damage"),
                "median_effective_damage_per_use": metrics.get(
                    "effective_damage_median_per_use"
                ),
                "damage_per_mana": metrics.get("damage_per_mana"),
                "effective_direct_damage_per_combat_turn": metrics.get(
                    "effective_direct_damage_per_combat_turn"
                ),
                "mean_mana_cost_per_use": metrics.get("mean_mana_cost_per_use"),
                "healing": metrics.get("healing"),
                "effect_applications": metrics.get("effect_applications"),
                "battle_contexts": sample_basis.get(
                    "battle_contexts", metrics.get("contexts")
                ),
                "battles_per_context": sample_basis.get("battles_per_context"),
                "independent_random_trials": sample_basis.get(
                    "independent_random_trials"
                ),
                "confidence": classification.get("confidence"),
            }
        )
    return skills


def _h14_scenarios(source: dict[str, Any]) -> list[dict[str, Any]]:
    scenarios = []
    for scenario in source["scenarios"]:
        strategies = {}
        for strategy_name, details in scenario["strategies"].items():
            aggregate = details["aggregate"]
            strategies[strategy_name] = {
                key: aggregate.get(key) for key in STRATEGY_METRICS
            }
        scenarios.append(
            {
                "scenario_id": scenario["scenario_id"],
                "scenario_name": scenario["scenario_name"],
                "party_size": scenario["party_size"],
                "enemy_size": scenario["enemy_size"],
                "seed_set": scenario["seed_set"],
                "strategies": strategies,
                "paired_vs_baseline": scenario.get("paired_vs_baseline", {}),
            }
        )
    return scenarios


def _recommendations(
    h12: dict[str, Any], h13: dict[str, Any], h14: dict[str, Any]
) -> list[dict[str, Any]]:
    findings = {finding["finding_id"]: finding for finding in h12["findings"]}

    def from_h12(
        finding_id: str,
        priority: str,
        title: str,
        next_experiment: str,
    ) -> dict[str, Any]:
        finding = findings[finding_id]
        return {
            "id": finding_id,
            "priority": priority,
            "title": title,
            "evidence": finding.get("facts"),
            "scenarios": finding.get("case_refs", []),
            "metrics": finding.get("facts"),
            "sample_counts": finding.get("sample_sizes", {}),
            "risk": finding.get("hypothesis"),
            "confidence": (
                "Baixa: evidência sintética determinística; a maioria dos "
                "contrastes citados tem uma execução por configuração."
            ),
            "next_experiment": next_experiment,
            "sources": ["H.12"],
        }

    recommendations = [
        from_h12(
            "synthetic-enemy-defense-threshold",
            "alta",
            "Validar a duração/derrota no contraste de defesa",
            "Executar o contraste pareado em snapshot canônico autorizado, "
            "controlando nível, ficha, equipamento, grupo e política.",
        ),
        from_h12(
            "synthetic-boss-party-size-threshold",
            "alta",
            "Investigar a sensibilidade de boss ao tamanho do grupo",
            "Repetir com encontros autorizados e separar tamanho, cura, "
            "iniciativa, equipamentos e composição.",
        ),
        from_h12(
            "synthetic-equipment-deltas",
            "média",
            "Comparar ganhos de ataque e defesa de equipamentos",
            "Comparar itens do catálogo autorizado por slot, raridade, custo "
            "e requisitos, mantendo o restante da ficha constante.",
        ),
        from_h12(
            "synthetic-direct-skill-efficiency",
            "média",
            "Verificar a eficiência relativa de habilidades diretas",
            "Comparar habilidades publicadas contra alvos neutros e resistentes, "
            "com mana disponível, cooldown e uso controlados.",
        ),
        {
            "id": "h14-policy-outcomes",
            "priority": "observação",
            "title": "Ampliar contextos de comparação das políticas de IA",
            "evidence": {
                "paired_comparisons_against_baseline": sum(
                    comparison.get("pair_count", 0)
                    for scenario in h14["scenarios"]
                    for name, comparison in scenario[
                        "paired_vs_baseline"
                    ].items()
                    if name != "baseline"
                ),
                "outcome_changes": sum(
                    pair.get("result_changed", False)
                    for scenario in h14["scenarios"]
                    for comparison in scenario[
                        "paired_vs_baseline"
                    ].values()
                    for pair in comparison.get("pairs", [])
                ),
            },
            "scenarios": [scenario["scenario_id"] for scenario in h14["scenarios"]],
            "metrics": [
                "desfecho pareado",
                "dano recebido",
                "mana consumida",
                "efeitos",
            ],
            "sample_counts": {
                "battles": h14["battle_count"],
                "scenarios": h14["scenario_count"],
                "seeds_per_scenario": len(h14["seeds"]),
            },
            "risk": (
                "Políticas diferem em seleção/recursos em alguns cenários, mas "
                "as repetições são determinísticas e não demonstram superioridade."
            ),
            "confidence": "Baixa para generalização; alta apenas para reprodutibilidade do lote.",
            "next_experiment": (
                "Adicionar cenários sintéticos que isolem decisões e, após "
                "autorização, avaliar um snapshot canônico; manter baseline oficial."
            ),
            "sources": ["H.14"],
        },
        {
            "id": "canonical-catalog-unassessed",
            "priority": "dados insuficientes",
            "title": "Não concluir balanceamento do catálogo canônico",
            "evidence": {
                "canonical_entities_loaded": False,
                "canonical_skill_count": None,
                "canonical_equipment_count": None,
            },
            "scenarios": [],
            "metrics": "Sem métricas de conteúdo canônico.",
            "sample_counts": {
                "canonical_trials": 0,
                "synthetic_skills_in_h13": len(h13["skills"]),
            },
            "risk": (
                "Aplicar mudanças oficiais com base em conteúdo sintético "
                "pode introduzir regressões ou balanceamento inadequado."
            ),
            "confidence": "Alta quanto à limitação: fontes H.12/H.13/H.14 declaram escopo sintético.",
            "next_experiment": (
                "Obter snapshot canônico sanitizado e versionado em ambiente "
                "isolado, com autorização explícita e metas de design definidas."
            ),
            "sources": ["H.12", "H.13", "H.14"],
        },
    ]
    return recommendations


def build_consolidated_report(
    h11_markdown: str,
    h12: dict[str, Any],
    h13: dict[str, Any],
    h14: dict[str, Any],
) -> dict[str, Any]:
    _require(h12.get("synthetic_only") is True, "H.12 não está marcado como sintético.")
    _require(h12.get("postgres_accessed") is False, "H.12 reporta acesso PostgreSQL.")
    _require(h13.get("source") == "synthetic-only", "H.13 não está marcado como sintético.")
    _require(
        h13.get("canonical_catalog_accessed") is False,
        "H.13 reporta acesso ao catálogo canônico.",
    )
    _require(h14.get("source") == "synthetic-only", "H.14 não está marcado como sintético.")
    _require(
        h14.get("canonical_ai_replaced") is False,
        "H.14 reporta substituição da IA canônica.",
    )
    h11 = _h11_summary(h11_markdown)
    cases = _h12_cases(h12)
    skills = _h13_skills(h13)
    scenarios = _h14_scenarios(h14)

    return {
        "stage": "H.15",
        "title": "Consolidação de relatórios quantitativos de combate",
        "scope": "synthetic-only",
        "canonical_balance_certified": False,
        "sources": {
            stage: {
                "file": filename,
                "scope": "synthetic-only",
                "summary": {
                    "H.11": "Benchmark e metodologia do simulador H.11.",
                    "H.12": "45 cenários/configurações comparativas; uma execução final por caso.",
                    "H.13": "6 habilidades sintéticas e 26 comparações por contexto.",
                    "H.14": "7 cenários, 6 políticas e 5 seeds determinísticas pareadas.",
                }[stage],
            }
            for stage, filename in SOURCE_FILES.items()
        },
        "population_policy": (
            "Não somar batalhas entre etapas nem agregar cenários incompatíveis: "
            "as matrizes diferem em objetivos, cenários e unidade amostral."
        ),
        "phases": {
            "H.11": h11,
            "H.12": {
                "battle_count_completed": h12["battle_count_completed"],
                "battle_count_requested": h12["battle_count_requested"],
                "scenario_count": h12["scenario_count"],
                "seed_count_per_case": h12["seed_count"],
                "failure_count": h12["failure_count"],
                "cases": cases,
                "paired_comparisons": h12["paired_comparisons"],
                "percentiles_available": ["p25", "p50", "p75", "p90"],
                "confidence_intervals_inferential": False,
            },
            "H.13": {
                "skill_count": len(skills),
                "comparison_count": len(h13["comparisons"]),
                "ai_observation_count": len(h13["ai_observations"]),
                "skills": skills,
                "conclusions": h13.get("conclusions", {}),
            },
            "H.14": {
                "scenario_count": h14["scenario_count"],
                "battle_count": h14["battle_count"],
                "simulation_failure_count": h14["simulation_failure_count"],
                "seeds": h14["seeds"],
                "strategies": h14["strategies"],
                "scenarios": scenarios,
                "conclusions": h14.get("conclusions", {}),
            },
        },
        "recommendations": _recommendations(h12, h13, h14),
        "validity_of_conclusions": {
            "synthetic_facts": [
                "H.11 executou 1.000 batalhas do benchmark low-vs-basic sem falhas; todas foram vitórias e o desvio padrão observado foi zero.",
                "H.12 completou 45 de 45 configurações sintéticas, com uma execução final por configuração e zero falhas.",
                "H.13 avaliou 6 habilidades sintéticas em 26 comparações de contexto; as classificações não descrevem o catálogo real.",
                "H.14 completou 210 batalhas sintéticas em 7 cenários e 6 políticas sem falhas; 0 de 175 comparações pareadas mudaram o desfecho.",
            ],
            "hypotheses_for_new_experiments": [
                "Os contrastes sintéticos de defesa, tamanho de grupo contra boss, equipamento e custo/eficiência de habilidade merecem validação controlada.",
                "As diferenças de seleção de ação/alvo e de recursos entre políticas H.14 podem orientar cenários experimentais adicionais.",
            ],
            "canonical_catalog_dependencies": [
                "Taxas de vitória, duração e sobrevivência com personagens, inimigos e bosses publicados.",
                "Curva de valor de equipamentos existentes e seus custos, slots e requisitos.",
                "Eficiência, disponibilidade e utilização das habilidades canônicas.",
                "Adequação da estratégia oficial ou parâmetros oficiais de combate.",
            ],
            "insufficient_evidence": [
                "Dominância, fraqueza ou desequilíbrio canônico.",
                "Inferência estatística populacional: o motor é determinístico e seeds repetidas não são ensaios aleatórios independentes.",
                "Comparação agregada de dano/eficiência entre cenários com composições ou condições diferentes.",
                "Impacto da progressão em builds reais: H.12 manteve atributos não derivados de HP/mana sem distribuição de pontos.",
            ],
        },
        "limitations": [
            "Nenhum relatório fonte usa entidades canônicas; H.12 não encontrou catálogo versionado no repositório.",
            "H.11/H.12/H.13/H.14 são desenhos e unidades de análise diferentes; os números não devem ser somados.",
            "Wilson em H.12/H.14 é nominal/descritivo; não é intervalo inferencial válido para repetições determinísticas.",
            "H.13 usa métricas diretas e não atribui com segurança dano contínuo ao autor; cura e efeitos não são comparáveis apenas por dano/mana.",
            "H.14 baseline continua referência e padrão; o relatório não seleciona política oficial.",
            "Não há visualizações gráficas binárias; este relatório usa tabelas e barras textuais para evitar dependências e misturas de cenários.",
        ],
    }


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/d"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _h12_metric(case: dict[str, Any], metric: str, statistic: str) -> Any:
    summary = case["metrics"].get(metric)
    return summary.get(statistic) if isinstance(summary, dict) else None


def report_to_markdown(report: dict[str, Any]) -> str:
    h11 = report["phases"]["H.11"]
    h12 = report["phases"]["H.12"]
    h13 = report["phases"]["H.13"]
    h14 = report["phases"]["H.14"]
    lines = [
        "# H.15 — Consolidação de relatórios quantitativos de combate",
        "",
        "> **Escopo sintético.** Este relatório não certifica o balanceamento canônico, não recomenda alterações de regras e não escolhe uma nova IA oficial.",
        "",
        "## Visão executiva",
        "",
        f"- **H.11:** {h11['battle_count']:,} batalhas no benchmark `low-vs-basic`, "
        f"{h11['wins']:,} vitórias e {h11['failure_count']} falhas; "
        f"{_fmt(h11['mean_logical_rounds'])} rodadas lógicas médias e "
        f"{_fmt(h11['mean_effective_damage_per_battle'])} dano efetivo médio.",
        f"- **H.12:** {h12['battle_count_completed']} de {h12['battle_count_requested']} "
        f"configurações concluídas, {h12['scenario_count']} casos e "
        f"{h12['failure_count']} falhas.",
        f"- **H.13:** {h13['skill_count']} habilidades sintéticas, "
        f"{h13['comparison_count']} contrastes por contexto e "
        f"{h13['ai_observation_count']} observações de seleção de IA.",
        f"- **H.14:** {h14['battle_count']} batalhas em {h14['scenario_count']} "
        f"cenários e {len(h14['strategies'])} políticas; "
        f"{h14['simulation_failure_count']} falhas; nenhum desfecho mudou em "
        "175 pares contra baseline.",
        "- Os totais das etapas **não são somados**: as populações e unidades de análise diferem.",
        "",
        "## Metodologia e rastreabilidade",
        "",
        "Os dados são extraídos dos relatórios H.11–H.14 existentes; este consolidador não executa batalhas, não recalcula fórmulas do motor e não acessa bancos. Cada tabela permanece separada por fase e cenário.",
        "",
        "| Etapa | Fonte original | Unidade e escopo |",
        "|---|---|---|",
    ]
    for stage, source in report["sources"].items():
        lines.append(
            f"| {stage} | [{source['file']}]({source['file']}) | {source['summary']} |"
        )
    lines.extend(
        [
            "",
            "### H.11 — Benchmark documentado",
            "",
            "| Cenário | Batalhas | Vitórias | Taxa | Turnos iniciados média/mediana | Rodadas médias | Dano efetivo médio | Desvio padrão reportado |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
            f"| `{h11['benchmark_scenario']}` | {h11['battle_count']} | {h11['wins']} | "
            f"{_fmt(h11['win_rate'] * 100)}% | "
            f"{_fmt(h11['mean_and_median_turns_initiated'])} | "
            f"{_fmt(h11['mean_logical_rounds'])} | "
            f"{_fmt(h11['mean_effective_damage_per_battle'])} | "
            f"{_fmt(h11['reported_population_stddev'])} |",
            "",
            "A taxa e a dispersão descrevem o cenário determinístico repetido; não são estimativas de taxa populacional.",
            "",
            "### H.12 — Resultados por configuração",
            "",
            "| Caso | Família | Vitórias | Derrotas | Sobrevivência do grupo | Turnos médios (mediana) | Dano efetivo médio (mediana; p25–p90) | Mana média | n |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for case in h12["cases"]:
        outcomes = case["result_counts"]
        turns = case["metrics"].get("turns")
        damage = case["metrics"].get("damage_effective")
        mana = case["metrics"].get("mana_consumed")
        damage_range = (
            f"{_fmt(damage.get('p25'))}–{_fmt(damage.get('p90'))}"
            if isinstance(damage, dict)
            else "n/d"
        )
        lines.append(
            f"| `{case['case_id']}` | {case['family']} | {outcomes.get('victory', 0)} | "
            f"{outcomes.get('defeat', 0)} | "
            f"{_fmt(case.get('party_survival_rate') * 100 if case.get('party_survival_rate') is not None else None)}% | "
            f"{_fmt(turns.get('mean') if isinstance(turns, dict) else None)} "
            f"({_fmt(turns.get('median') if isinstance(turns, dict) else None)}) | "
            f"{_fmt(damage.get('mean') if isinstance(damage, dict) else None)} "
            f"({_fmt(damage.get('median') if isinstance(damage, dict) else None)}; "
            f"{damage_range}) | "
            f"{_fmt(mana.get('mean') if isinstance(mana, dict) else None)} | "
            f"{case['sample_size']} |"
        )
    lines.extend(
        [
            "",
            "As estatísticas de H.12 são exatas para as configurações determinísticas observadas; há uma execução final por caso. Percentis nearest-rank p25/p50/p75/p90 descrevem as observações da fonte e não representam dispersão populacional.",
            "",
            "### H.13 — Habilidades (cada linha sintética; não ordenar como ranking canônico)",
            "",
            "| Habilidade sintética | Tipo | Usos | Dano efetivo direto | Mediana por uso | Dano/mana | Dano/turno | Custo médio | Efeitos | Contextos | Classificação exploratória |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for skill in h13["skills"]:
        lines.append(
            f"| {skill['skill']} | {skill.get('skill_type') or skill.get('category') or 'n/d'} | "
            f"{_fmt(skill.get('uses'))} | {_fmt(skill.get('effective_direct_damage'))} | "
            f"{_fmt(skill.get('median_effective_damage_per_use'))} | "
            f"{_fmt(skill.get('damage_per_mana'))} | "
            f"{_fmt(skill.get('effective_direct_damage_per_combat_turn'))} | "
            f"{_fmt(skill.get('mean_mana_cost_per_use'))} | "
            f"{_fmt(skill.get('effect_applications'))} | "
            f"{_fmt(skill.get('battle_contexts'))} | "
            f"{skill.get('classification') or 'dados insuficientes'} |"
        )
    lines.extend(
        [
            "",
            "H.13 registrou 17 de 26 contrastes com benefício pareado conforme seu critério exploratório; essa contagem não equivale a significância, e as comparações compartilham contextos/seed determinísticos. Cura, efeitos e dano direto têm utilidades distintas.",
            "",
            "### H.14 — Comparação de políticas, separada por cenário",
            "",
            "Barras de taxa de vitória são comparáveis apenas dentro do mesmo cenário; cada ponto equivale a uma batalha dentre cinco.",
            "",
        ]
    )
    for scenario in h14["scenarios"]:
        lines.extend(
            [
                f"#### {scenario['scenario_name']} (`{scenario['scenario_id']}`)",
                "",
                f"Composição: {scenario['party_size']} jogador(es) × "
                f"{scenario['enemy_size']} inimigo(s); amostras determinísticas "
                f"pareadas: {len(scenario['seed_set'])}.",
                "",
                "| Política | Vitórias/5 | Gráfico | Taxa | Sobrevivência | Dano efetivo do grupo | Dano recebido | Mana IA | Efeitos IA | Rodadas médias |",
                "|---|---:|:---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for name, metrics in scenario["strategies"].items():
            counts = metrics.get("outcome_counts") or {}
            wins = counts.get("victory", 0)
            sample_size = metrics.get("sample_size", 0)
            chart_bar = (
                "#" * round((metrics.get("win_rate") or 0) * sample_size)
                + "-" * max(0, sample_size - round((metrics.get("win_rate") or 0) * sample_size))
            )
            lines.append(
                f"| {name} | {wins}/{sample_size} | `{chart_bar}` | "
                f"{_fmt((metrics.get('win_rate') or 0) * 100)}% | "
                f"{_fmt(metrics.get('mean_party_survival_rate') * 100 if metrics.get('mean_party_survival_rate') is not None else None)}% | "
                f"{_fmt(metrics.get('mean_party_damage_effective'))} | "
                f"{_fmt(metrics.get('mean_party_damage_received_effective'))} | "
                f"{_fmt(metrics.get('mean_enemy_mana_consumed'))} | "
                f"{_fmt(metrics.get('mean_enemy_effects_applied'))} | "
                f"{_fmt(metrics.get('mean_logical_duration_rounds'))} |"
            )
        lines.append("")
    lines.extend(
        [
            "Em H.14, 0 de 175 comparações pareadas contra baseline mudaram o desfecho. A política pode alterar ação, alvo, recursos ou duração sem alterar vitória/derrota; não se declara superioridade. Os intervalos Wilson de origem são nominais e não inferenciais.",
            "",
            "## Recomendações",
            "",
            "Não há recomendação crítica sustentada pelas fontes. Prioridades abaixo indicam ordem de investigação, não severidade canônica.",
            "",
            "| Prioridade | Recomendação | Evidência | Cenários | Métricas | Amostras | Confiança | Próximo experimento |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for item in report["recommendations"]:
        evidence = json.dumps(item["evidence"], ensure_ascii=False, separators=(",", ":"))
        metrics = json.dumps(item["metrics"], ensure_ascii=False, separators=(",", ":"))
        count = json.dumps(item["sample_counts"], ensure_ascii=False, separators=(",", ":"))
        lines.append(
            f"| {item['priority']} | {item['title']} | `{evidence}` | "
            f"`{json.dumps(item['scenarios'], ensure_ascii=False)}` | `{metrics}` | `{count}` | "
            f"{item['confidence']} | {item['next_experiment']} |"
        )
    lines.extend(
        [
            "",
            "## Validade das conclusões",
            "",
            "### Fatos demonstrados por simulações sintéticas",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["validity_of_conclusions"]["synthetic_facts"])
    lines.extend(["", "### Hipóteses que precisam de novos experimentos", ""])
    lines.extend(
        f"- {item}"
        for item in report["validity_of_conclusions"]["hypotheses_for_new_experiments"]
    )
    lines.extend(["", "### Conclusões dependentes do catálogo canônico", ""])
    lines.extend(
        f"- {item}"
        for item in report["validity_of_conclusions"]["canonical_catalog_dependencies"]
    )
    lines.extend(["", "### Questões sem evidência suficiente", ""])
    lines.extend(
        f"- {item}"
        for item in report["validity_of_conclusions"]["insufficient_evidence"]
    )
    lines.extend(["", "## Limitações e próximos passos", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.extend(
        [
            "- Próximo passo seguro: obter autorização e um snapshot canônico sanitizado/versionado em ambiente isolado, definir metas de design e executar comparações controladas sem alterar regras nesta etapa.",
            "- CSVs detalhados: `etapa-h15-combat-scenarios.csv`, `etapa-h15-combat-skills.csv`, `etapa-h15-combat-strategies.csv` e `etapa-h15-combat-recommendations.csv`.",
            "",
        ]
    )
    return "\n".join(lines)


def _scenario_csv(report: dict[str, Any]) -> str:
    fields = [
        "source_stage",
        "scenario_id",
        "family",
        "sample_size",
        "wins",
        "defeats",
        "draws",
        "turns_mean",
        "turns_median",
        "damage_effective_mean",
        "damage_effective_median",
        "damage_p25",
        "damage_p90",
        "mana_consumed_mean",
        "party_survival_rate",
        "win_rate",
        "inferential_ci_valid",
    ]
    stream, writer = _csv_writer(fields)
    for case in report["phases"]["H.12"]["cases"]:
        turns = case["metrics"].get("turns") or {}
        damage = case["metrics"].get("damage_effective") or {}
        mana = case["metrics"].get("mana_consumed") or {}
        outcomes = case["result_counts"]
        writer.writerow(
            {
                "source_stage": "H.12",
                "scenario_id": case["case_id"],
                "family": case["family"],
                "sample_size": case["sample_size"],
                "wins": outcomes.get("victory", 0),
                "defeats": outcomes.get("defeat", 0),
                "draws": outcomes.get("draw", 0),
                "turns_mean": turns.get("mean"),
                "turns_median": turns.get("median"),
                "damage_effective_mean": damage.get("mean"),
                "damage_effective_median": damage.get("median"),
                "damage_p25": damage.get("p25"),
                "damage_p90": damage.get("p90"),
                "mana_consumed_mean": mana.get("mean"),
                "party_survival_rate": case.get("party_survival_rate"),
                "win_rate": case.get("win_rate"),
                "inferential_ci_valid": case["inferential_ci_valid"],
            }
        )
    for scenario in report["phases"]["H.14"]["scenarios"]:
        for policy, metrics in scenario["strategies"].items():
            counts = metrics.get("outcome_counts") or {}
            writer.writerow(
                {
                    "source_stage": f"H.14:{policy}",
                    "scenario_id": scenario["scenario_id"],
                    "family": "ai-strategy",
                    "sample_size": metrics.get("sample_size"),
                    "wins": counts.get("victory", 0),
                    "defeats": counts.get("defeat", 0),
                    "draws": counts.get("draw", 0),
                    "turns_mean": metrics.get("mean_logical_duration_rounds"),
                    "damage_effective_mean": metrics.get(
                        "mean_party_damage_effective"
                    ),
                    "mana_consumed_mean": metrics.get("mean_enemy_mana_consumed"),
                    "party_survival_rate": metrics.get("mean_party_survival_rate"),
                    "win_rate": metrics.get("win_rate"),
                    "inferential_ci_valid": False,
                }
            )
    return stream.getvalue()


def _skills_csv(report: dict[str, Any]) -> str:
    fields = [
        "source_stage",
        "skill",
        "category",
        "skill_type",
        "classification",
        "uses",
        "effective_direct_damage",
        "median_effective_damage_per_use",
        "damage_per_mana",
        "effective_direct_damage_per_combat_turn",
        "mean_mana_cost_per_use",
        "healing",
        "effect_applications",
        "battle_contexts",
        "battles_per_context",
        "independent_random_trials",
        "confidence",
    ]
    stream, writer = _csv_writer(fields)
    for skill in report["phases"]["H.13"]["skills"]:
        writer.writerow({"source_stage": "H.13", **skill})
    return stream.getvalue()


def _strategies_csv(report: dict[str, Any]) -> str:
    fields = [
        "source_stage",
        "scenario_id",
        "scenario_name",
        "party_size",
        "enemy_size",
        "strategy",
        "sample_size",
        "wins",
        "defeats",
        "draws",
        "turn_limit",
        "win_rate",
        "wilson_95_nominal",
        "mean_party_survival_rate",
        "mean_party_damage_effective",
        "mean_party_damage_received_effective",
        "mean_enemy_mana_consumed",
        "mean_enemy_skill_damage_per_mana",
        "mean_enemy_effects_applied",
        "mean_healing_effective",
        "mean_logical_duration_rounds",
        "mean_players_defeated",
        "mean_enemies_defeated",
        "mean_enemy_target_focus_share",
        "mean_party_target_focus_share",
    ]
    stream, writer = _csv_writer(fields)
    for scenario in report["phases"]["H.14"]["scenarios"]:
        for strategy, metrics in scenario["strategies"].items():
            counts = metrics.get("outcome_counts") or {}
            interval = metrics.get("win_rate_wilson_95_nominal")
            writer.writerow(
                {
                    "source_stage": "H.14",
                    "scenario_id": scenario["scenario_id"],
                    "scenario_name": scenario["scenario_name"],
                    "party_size": scenario["party_size"],
                    "enemy_size": scenario["enemy_size"],
                    "strategy": strategy,
                    "sample_size": metrics.get("sample_size"),
                    "wins": counts.get("victory", 0),
                    "defeats": counts.get("defeat", 0),
                    "draws": counts.get("draw", 0),
                    "turn_limit": counts.get("turn_limit", 0),
                    "win_rate": metrics.get("win_rate"),
                    "wilson_95_nominal": json.dumps(interval) if interval else "",
                    **{
                        key: metrics.get(key)
                        for key in fields
                        if key.startswith("mean_")
                    },
                }
            )
    return stream.getvalue()


def _recommendations_csv(report: dict[str, Any]) -> str:
    fields = [
        "id",
        "priority",
        "title",
        "scenarios",
        "sample_counts",
        "evidence",
        "metrics",
        "risk",
        "confidence",
        "next_experiment",
        "sources",
    ]
    stream, writer = _csv_writer(fields)
    for item in report["recommendations"]:
        writer.writerow(
            {
                "id": item["id"],
                "priority": item["priority"],
                "title": item["title"],
                "scenarios": json.dumps(item["scenarios"], ensure_ascii=False),
                "sample_counts": json.dumps(
                    item["sample_counts"], ensure_ascii=False
                ),
                "evidence": json.dumps(item["evidence"], ensure_ascii=False),
                "metrics": json.dumps(item["metrics"], ensure_ascii=False),
                "risk": item["risk"],
                "confidence": item["confidence"],
                "next_experiment": item["next_experiment"],
                "sources": json.dumps(item["sources"], ensure_ascii=False),
            }
        )
    return stream.getvalue()


def _csv_writer(
    fields: list[str],
) -> tuple[csv.StringIO, csv.DictWriter]:
    stream = csv.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    return stream, writer


def write_reports(report: dict[str, Any], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "etapa-h15-combat-balance-report.md": report_to_markdown(report),
        "etapa-h15-combat-balance-report.json": json.dumps(
            report, ensure_ascii=False, indent=2
        )
        + "\n",
        "etapa-h15-combat-scenarios.csv": _scenario_csv(report),
        "etapa-h15-combat-skills.csv": _skills_csv(report),
        "etapa-h15-combat-strategies.csv": _strategies_csv(report),
        "etapa-h15-combat-recommendations.csv": _recommendations_csv(report),
    }
    paths = []
    for filename, contents in outputs.items():
        path = output_dir / filename
        path.write_text(contents, encoding="utf-8", newline="")
        paths.append(path)
    return paths


def consolidate_directory(
    source_dir: Path, output_dir: Path
) -> list[Path]:
    h11_path = source_dir / SOURCE_FILES["H.11"]
    h11_markdown = h11_path.read_text(encoding="utf-8")
    h12 = json.loads((source_dir / SOURCE_FILES["H.12"]).read_text(encoding="utf-8"))
    h13 = json.loads((source_dir / SOURCE_FILES["H.13"]).read_text(encoding="utf-8"))
    h14 = json.loads((source_dir / SOURCE_FILES["H.14"]).read_text(encoding="utf-8"))
    return write_reports(
        build_consolidated_report(h11_markdown, h12, h13, h14), output_dir
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Consolida os relatórios sintéticos H.11–H.14."
    )
    parser.add_argument("--source-dir", type=Path, default=Path("docs"))
    parser.add_argument("--output-dir", type=Path, default=Path("docs"))
    arguments = parser.parse_args()
    for path in consolidate_directory(arguments.source_dir, arguments.output_dir):
        print(path)


if __name__ == "__main__":
    main()
