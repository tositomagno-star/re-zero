from __future__ import annotations

import argparse
import asyncio
import csv
from dataclasses import dataclass
import io
import json
import math
from pathlib import Path
import statistics
from typing import Any, Iterable

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
from app.services.progression import (
    ATTRIBUTE_POINTS_PER_LEVEL,
    BASE_XP_PER_LEVEL,
    HP_PER_LEVEL,
    MANA_PER_LEVEL,
    MAX_CHARACTER_LEVEL,
)

SEEDS = (100,)
CONFIDENCE_LEVEL = 0.95
_SUMMARY_METRICS = (
    "turns",
    "logical_duration_rounds",
    "party_damage_dealt_effective",
    "party_damage_received_effective",
    "enemy_damage_dealt_effective",
    "party_healing_effective",
    "total_mana_consumed",
)


@dataclass(frozen=True)
class AnalysisCase:
    case_id: str
    family: str
    scenario: BattleScenario
    control: str
    comparison: str
    party_strategy: str = "effective_damage"
    enemy_strategy: str = "baseline"


def wilson_interval(successes: int, trials: int, z_score: float = 1.959963984540054) -> tuple[float, float]:
    if trials <= 0 or successes < 0 or successes > trials or z_score <= 0:
        raise ValueError("Wilson interval requires valid counts and a positive z score.")
    proportion = successes / trials
    z_squared = z_score * z_score
    denominator = 1 + z_squared / trials
    center = (proportion + z_squared / (2 * trials)) / denominator
    margin = (
        z_score
        * math.sqrt(
            proportion * (1 - proportion) / trials
            + z_squared / (4 * trials * trials)
        )
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _case(
    case_id: str,
    family: str,
    players: tuple[CombatantSpec, ...],
    enemies: tuple[CombatantSpec, ...],
    *,
    control: str,
    comparison: str,
    max_turns: int = 1000,
) -> AnalysisCase:
    scenario = BattleScenario(
        scenario_id=f"h12-{case_id}",
        name=f"H.12 synthetic: {case_id}",
        participants=(*players, *enemies),
        max_turns=max_turns,
    )
    return AnalysisCase(case_id, family, scenario, control, comparison)


def build_analysis_cases() -> tuple[AnalysisCase, ...]:
    cases = [
        AnalysisCase(
            f"h11-{scenario_id}",
            "h11-synthetic-scenarios",
            scenario,
            "Dados e parâmetros originais do cenário H.11",
            "Execução de referência sem alterações",
        )
        for scenario_id, scenario in SYNTHETIC_SCENARIOS.items()
    ]
    cases.append(
        AnalysisCase(
            "healing-survival-policy",
            "healing-strategy",
            SYNTHETIC_SCENARIOS["defense-and-healing"],
            "Mesmo cenário H.11 com política do jogador effective_damage",
            "Política experimental survival; healing priorizado quando HP <= 50%",
            party_strategy="survival",
        )
    )

    level_enemy = CombatantSpec("Alvo controlado", "enemy", 1, 16, 0, 3, defense=1, speed=5)
    for level in (1, 5, 15, 50, 100, 1000, MAX_CHARACTER_LEVEL):
        levels_gained = level - 1
        player = CombatantSpec(
            f"Personagem nível {level}",
            "player",
            level,
            24 + levels_gained * HP_PER_LEVEL,
            6 + levels_gained * MANA_PER_LEVEL,
            5,
            magic_attack=5,
            defense=2,
            magic_defense=2,
            speed=8,
        )
        cases.append(
            _case(
                f"level-{level:05d}",
                "level-matrix",
                (player,),
                (level_enemy,),
                control=(
                    f"Nível 1 base; HP +{HP_PER_LEVEL}, mana +{MANA_PER_LEVEL} e "
                    f"{ATTRIBUTE_POINTS_PER_LEVEL} ponto de atributo por nível; "
                    "pontos não distribuídos e demais atributos constantes."
                ),
                comparison=f"Nível {level}",
            )
        )

    archetype_enemy = CombatantSpec("Alvo de arquétipo", "enemy", 10, 90, 0, 10, defense=8, speed=7)
    archetypes = (
        (
            "physical",
            CombatantSpec(
                "Configuração física", "player", 10, 80, 20, 18, 8, 8, 8, 8
            ),
        ),
        (
            "magic",
            CombatantSpec(
                "Configuração mágica",
                "player",
                10,
                80,
                20,
                8,
                18,
                8,
                8,
                8,
                skills=(SkillSpec("Feitiço sintético", "magic", 12, 5, "arcane"),),
            ),
        ),
        (
            "defensive",
            CombatantSpec(
                "Configuração defensiva", "player", 10, 80, 20, 12, 10, 12, 8, 8
            ),
        ),
    )
    for case_id, player in archetypes:
        cases.append(
            _case(
                f"archetype-{case_id}",
                "archetypes",
                (player,),
                (archetype_enemy,),
                control="Nível 10, HP/mana iniciais iguais, mesmo alvo e orçamento sintético declarado.",
                comparison=case_id,
            )
        )

    enemy_player = CombatantSpec("Aventureiro controlado", "player", 10, 100, 20, 16, 12, 8, 8, 10)
    enemy_variants = (
        ("baseline", 75, 10, 5, 8),
        ("high-hp", 150, 10, 5, 8),
        ("high-attack", 75, 20, 5, 8),
        ("high-defense", 75, 10, 15, 8),
        ("high-speed", 75, 10, 5, 15),
    )
    for variant, hp, attack, defense, speed in enemy_variants:
        enemy = CombatantSpec(
            f"Inimigo sintético {variant}", "enemy", 10, hp, 0, attack,
            defense=defense, speed=speed,
        )
        cases.append(
            _case(
                f"enemy-{variant}",
                "enemy-archetypes",
                (enemy_player,),
                (enemy,),
                control="Mesmo personagem, nível, cenário e seed; somente o atributo indicado varia.",
                comparison=variant,
            )
        )

    boss = CombatantSpec(
        "Boss sintético controlado", "enemy", 12, 220, 20, 16, 12, 12, 10, 8, is_boss=True
    )
    for party_size in range(1, 6):
        party = tuple(
            CombatantSpec(
                f"Aventureiro {index}",
                "player",
                10,
                80,
                15,
                14,
                10,
                8,
                8,
                10,
            )
            for index in range(1, party_size + 1)
        )
        cases.append(
            _case(
                f"boss-party-{party_size}",
                "boss-party-scaling",
                party,
                (boss,),
                control="Mesmo boss sintético e membros idênticos; somente o tamanho do grupo varia.",
                comparison=f"{party_size} personagem(is)",
            )
        )

    equipment_player = (CombatantSpec("Portador", "player", 10, 80, 20, 14, 8, 8, 8, 10),)
    equipment_enemy = (CombatantSpec("Alvo de equipamento", "enemy", 10, 90, 0, 10, defense=8, speed=7),)
    equipment_variants = (
        ("none", equipment_player[0]),
        ("weapon-plus-6-attack", CombatantSpec("Portador", "player", 10, 80, 20, 20, 8, 8, 8, 10)),
        ("armor-plus-6-defense", CombatantSpec("Portador", "player", 10, 80, 20, 14, 8, 14, 8, 10)),
    )
    for variant, player in equipment_variants:
        cases.append(
            _case(
                f"equipment-{variant}",
                "equipment-deltas",
                (player,),
                equipment_enemy,
                control="Mesmo personagem, nível, recursos e inimigo; delta sintético aditivo isolado.",
                comparison=variant,
            )
        )

    skill_user = dict(
        name="Usuário de habilidade",
        side="player",
        level=10,
        hp=80,
        mana=20,
        attack=14,
        magic_attack=14,
        defense=8,
        magic_defense=8,
        speed=10,
    )
    skill_target = CombatantSpec("Alvo de habilidade", "enemy", 10, 90, 0, 10, defense=8, magic_defense=8, speed=7)
    skill_variants = (
        ("no-skill", ()),
        ("physical-skill", (SkillSpec("Golpe sintético", "physical", 12, 4, "physical"),)),
        ("magic-skill", (SkillSpec("Magia sintética", "magic", 12, 4, "arcane"),)),
        (
            "damage-over-time",
            (
                SkillSpec(
                    "Veneno sintético",
                    "magic",
                    5,
                    4,
                    "poison",
                    additional_effects={
                        "effect_type": "damage_over_time",
                        "damage_per_turn": 3,
                        "duration": 3,
                    },
                ),
            ),
        ),
    )
    for variant, skills in skill_variants:
        player = CombatantSpec(**skill_user, skills=skills)
        cases.append(
            _case(
                f"skill-{variant}",
                "skill-comparison",
                (player,),
                (skill_target,),
                control="Mesmo atacante, alvo, nível e recursos; muda apenas a habilidade disponível.",
                comparison=variant,
            )
        )

    group_boss = CombatantSpec(
        "Boss de composição sintético", "enemy", 12, 260, 20, 16, 12, 12, 10, 8, is_boss=True
    )
    group_members = {
        "offensive": CombatantSpec("Atacante", "player", 10, 75, 12, 20, 8, 6, 6, 10),
        "defensive": CombatantSpec("Defensor", "player", 10, 100, 12, 12, 8, 14, 10, 8),
        "magic-focused": CombatantSpec(
            "Arcanista", "player", 10, 75, 24, 8, 18, 6, 8, 9,
            skills=(SkillSpec("Rajada sintética", "magic", 12, 4, "arcane"),),
        ),
        "balanced": CombatantSpec(
            "Combatente equilibrado", "player", 10, 82, 18, 14, 12, 9, 9, 9
        ),
    }
    for composition, member in group_members.items():
        party = tuple(
            CombatantSpec(
                name=f"{member.name} {index}",
                side=member.side,
                level=member.level,
                hp=member.hp,
                mana=member.mana,
                attack=member.attack,
                magic_attack=member.magic_attack,
                defense=member.defense,
                magic_defense=member.magic_defense,
                speed=member.speed,
                skills=member.skills,
            )
            for index in range(1, 4)
        )
        cases.append(
            _case(
                f"group-{composition}",
                "group-compositions",
                party,
                (group_boss,),
                control="Três membros de um arquétipo, mesmo boss, nível e política do jogador.",
                comparison=composition,
            )
        )
    return tuple(cases)


def _compact_observation(result: dict[str, Any]) -> dict[str, Any]:
    participants = result["participants"]
    party = [item for item in participants if item["side"] == "player"]
    enemies = [item for item in participants if item["side"] == "enemy"]
    return {
        "seed": result["seed"],
        "result": result["result"],
        "turns": result["turns"],
        "logical_duration_rounds": result["logical_duration_rounds"],
        "actions_executed": result["actions_executed"],
        "total_damage_effective": result["total_damage_effective"],
        "total_damage_received_effective": result["total_damage_received_effective"],
        "total_healing_effective": result["total_healing_effective"],
        "total_mana_consumed": result["total_mana_consumed"],
        "players_surviving": result["players_surviving"],
        "enemies_surviving": result["enemies_surviving"],
        "party_damage_dealt_effective": sum(item["damage_effective"] for item in party),
        "party_damage_received_effective": sum(
            item["damage_received_effective"] for item in party
        ),
        "enemy_damage_dealt_effective": sum(item["damage_effective"] for item in enemies),
        "party_healing_effective": sum(item["healing_effective"] for item in party),
        "participants": participants,
        "skills": result["skills"],
    }


def _describe(values: list[float]) -> dict[str, float | int | None]:
    ordered = sorted(values)
    if not ordered:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "population_stddev": None,
            "min": None,
            "max": None,
            "p25": None,
            "p50": None,
            "p75": None,
            "p90": None,
        }

    def percentile(fraction: float) -> float:
        return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]

    return {
        "count": len(ordered),
        "mean": statistics.fmean(ordered),
        "median": statistics.median(ordered),
        "population_stddev": statistics.pstdev(ordered),
        "min": ordered[0],
        "max": ordered[-1],
        "p25": percentile(0.25),
        "p50": percentile(0.50),
        "p75": percentile(0.75),
        "p90": percentile(0.90),
    }


def _pair_summary(reference: dict[str, Any], comparison: dict[str, Any]) -> dict[str, Any]:
    reference_by_seed = {item["seed"]: item for item in reference["observations"]}
    comparison_by_seed = {item["seed"]: item for item in comparison["observations"]}
    shared_seeds = sorted(reference_by_seed.keys() & comparison_by_seed.keys())
    deltas: dict[str, float] = {}
    for metric in _SUMMARY_METRICS:
        values = [
            float(comparison_by_seed[seed][metric] - reference_by_seed[seed][metric])
            for seed in shared_seeds
        ]
        deltas[metric] = statistics.fmean(values) if values else 0.0
    win_deltas = [
        int(comparison_by_seed[seed]["result"] == "victory")
        - int(reference_by_seed[seed]["result"] == "victory")
        for seed in shared_seeds
    ]
    return {
        "reference_case": reference["case_id"],
        "comparison_case": comparison["case_id"],
        "paired_seed_count": len(shared_seeds),
        "seeds": shared_seeds,
        "mean_paired_win_rate_delta": statistics.fmean(win_deltas) if win_deltas else 0.0,
        "mean_paired_metric_deltas": deltas,
        "inferential_ci": None,
        "ci_note": (
            "Não estimado: o motor é determinístico e os seeds não induzem observações "
            "aleatórias independentes."
        ),
    }


def _comparison_pairs(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["case_id"]: item for item in cases}
    pairs: list[tuple[str, str]] = []
    pairs.extend((f"level-{1:05d}", f"level-{level:05d}") for level in (5, 15, 50, 100, 1000, MAX_CHARACTER_LEVEL))
    pairs.extend(("archetype-physical", f"archetype-{role}") for role in ("magic", "defensive"))
    pairs.extend(("enemy-baseline", f"enemy-{variant}") for variant in ("high-hp", "high-attack", "high-defense", "high-speed"))
    pairs.extend(("boss-party-1", f"boss-party-{size}") for size in range(2, 6))
    pairs.extend(("equipment-none", f"equipment-{variant}") for variant in ("weapon-plus-6-attack", "armor-plus-6-defense"))
    pairs.extend(("skill-no-skill", f"skill-{variant}") for variant in ("physical-skill", "magic-skill", "damage-over-time"))
    pairs.extend(("group-balanced", f"group-{role}") for role in ("offensive", "defensive", "magic-focused"))
    pairs.append(("h11-defense-and-healing", "healing-survival-policy"))
    return [
        _pair_summary(by_id[reference_id], by_id[comparison_id])
        for reference_id, comparison_id in pairs
        if reference_id in by_id and comparison_id in by_id
    ]


def _build_findings(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["case_id"]: item for item in cases}

    def observation(case_id: str) -> dict[str, Any]:
        return by_id[case_id]["observations"][0]

    def sample_size(case_id: str) -> int:
        return len(by_id[case_id]["observations"])

    findings: list[dict[str, Any]] = []
    if {"enemy-baseline", "enemy-high-defense"} <= by_id.keys():
        baseline = observation("enemy-baseline")
        high_defense = observation("enemy-high-defense")
        findings.append(
            {
                "finding_id": "synthetic-enemy-defense-threshold",
                "severity": "high-synthetic-signal",
                "scope": "synthetic-only",
                "case_refs": ["enemy-baseline", "enemy-high-defense"],
                "sample_sizes": {
                    "enemy-baseline": sample_size("enemy-baseline"),
                    "enemy-high-defense": sample_size("enemy-high-defense"),
                },
                "facts": {
                    "baseline_result": baseline["result"],
                    "high_defense_result": high_defense["result"],
                    "baseline_turns": baseline["turns"],
                    "high_defense_turns": high_defense["turns"],
                    "baseline_party_damage_received": baseline[
                        "party_damage_received_effective"
                    ],
                    "high_defense_party_damage_received": high_defense[
                        "party_damage_received_effective"
                    ],
                },
                "hypothesis": (
                    "Valores altos de defesa podem prolongar o combate até o dano mínimo "
                    "permitir desgaste do grupo."
                ),
                "recommendation": (
                    "Parear conteúdo canônico e personagens por nível antes de considerar "
                    "qualquer ajuste."
                ),
            }
        )
    if {"boss-party-4", "boss-party-5"} <= by_id.keys():
        four = observation("boss-party-4")
        five = observation("boss-party-5")
        findings.append(
            {
                "finding_id": "synthetic-boss-party-size-threshold",
                "severity": "high-synthetic-signal",
                "scope": "synthetic-only",
                "case_refs": ["boss-party-4", "boss-party-5"],
                "sample_sizes": {
                    "boss-party-4": sample_size("boss-party-4"),
                    "boss-party-5": sample_size("boss-party-5"),
                },
                "facts": {
                    "four_player_result": four["result"],
                    "five_player_result": five["result"],
                    "four_player_turns": four["turns"],
                    "five_player_turns": five["turns"],
                    "four_player_damage_received": four["party_damage_received_effective"],
                    "five_player_damage_received": five["party_damage_received_effective"],
                },
                "hypothesis": (
                    "A cadência de ações combinada ao HP/defesa do boss cria um limiar de "
                    "vitória na quinta ação de jogador."
                ),
                "recommendation": (
                    "Validar com composições e bosses canônicos; separar o efeito do tamanho "
                    "do grupo de cura, equipamento e iniciativa."
                ),
            }
        )
    if {"equipment-none", "equipment-weapon-plus-6-attack", "equipment-armor-plus-6-defense"} <= by_id.keys():
        baseline = observation("equipment-none")
        weapon = observation("equipment-weapon-plus-6-attack")
        armor = observation("equipment-armor-plus-6-defense")
        findings.append(
            {
                "finding_id": "synthetic-equipment-deltas",
                "severity": "moderate-synthetic-signal",
                "scope": "synthetic-only",
                "case_refs": [
                    "equipment-none",
                    "equipment-weapon-plus-6-attack",
                    "equipment-armor-plus-6-defense",
                ],
                "sample_sizes": {
                    "equipment-none": sample_size("equipment-none"),
                    "equipment-weapon-plus-6-attack": sample_size(
                        "equipment-weapon-plus-6-attack"
                    ),
                    "equipment-armor-plus-6-defense": sample_size(
                        "equipment-armor-plus-6-defense"
                    ),
                },
                "facts": {
                    "baseline_turns": baseline["turns"],
                    "attack_delta_turns": weapon["turns"],
                    "defense_delta_turns": armor["turns"],
                    "baseline_party_damage_received": baseline[
                        "party_damage_received_effective"
                    ],
                    "attack_delta_party_damage_received": weapon[
                        "party_damage_received_effective"
                    ],
                    "defense_delta_party_damage_received": armor[
                        "party_damage_received_effective"
                    ],
                },
                "hypothesis": (
                    "Benefícios ofensivos e defensivos podem alterar dimensões diferentes "
                    "de duração e sobrevivência."
                ),
                "recommendation": (
                    "Comparar equipamentos publicados por custo, slot, requisito e "
                    "progressão, mantendo o restante da ficha constante."
                ),
            }
        )
    if {"skill-no-skill", "skill-physical-skill", "skill-magic-skill"} <= by_id.keys():
        baseline = observation("skill-no-skill")
        physical = observation("skill-physical-skill")
        magic = observation("skill-magic-skill")
        findings.append(
            {
                "finding_id": "synthetic-direct-skill-efficiency",
                "severity": "moderate-synthetic-signal",
                "scope": "synthetic-only",
                "case_refs": [
                    "skill-no-skill",
                    "skill-physical-skill",
                    "skill-magic-skill",
                ],
                "sample_sizes": {
                    "skill-no-skill": sample_size("skill-no-skill"),
                    "skill-physical-skill": sample_size("skill-physical-skill"),
                    "skill-magic-skill": sample_size("skill-magic-skill"),
                },
                "facts": {
                    "baseline_turns": baseline["turns"],
                    "physical_skill_turns": physical["turns"],
                    "magic_skill_turns": magic["turns"],
                    "baseline_party_damage_received": baseline[
                        "party_damage_received_effective"
                    ],
                    "physical_skill_party_damage_received": physical[
                        "party_damage_received_effective"
                    ],
                    "physical_skill_mana": physical["total_mana_consumed"],
                    "magic_skill_mana": magic["total_mana_consumed"],
                },
                "hypothesis": (
                    "Potência direta e custo de mana podem tornar skills mais eficientes "
                    "em alvos sem resistência."
                ),
                "recommendation": (
                    "Validar custos, cooldowns e tipos de defesa contra habilidades "
                    "publicadas e inimigos com resistências reais."
                ),
            }
        )
    if {"level-00001", f"level-{MAX_CHARACTER_LEVEL:05d}"} <= by_id.keys():
        level_one = observation("level-00001")
        max_level = observation(f"level-{MAX_CHARACTER_LEVEL:05d}")
        findings.append(
            {
                "finding_id": "synthetic-level-isolation",
                "severity": "low-observational",
                "scope": "synthetic-only",
                "case_refs": ["level-00001", f"level-{MAX_CHARACTER_LEVEL:05d}"],
                "sample_sizes": {
                    "level-00001": sample_size("level-00001"),
                    f"level-{MAX_CHARACTER_LEVEL:05d}": sample_size(
                        f"level-{MAX_CHARACTER_LEVEL:05d}"
                    ),
                },
                "facts": {
                    "level_one_turns": level_one["turns"],
                    "max_level_turns": max_level["turns"],
                    "level_one_party_damage": level_one["party_damage_dealt_effective"],
                    "max_level_party_damage": max_level[
                        "party_damage_dealt_effective"
                    ],
                    "level_one_hp": by_id["level-00001"]["scenario"]["participants"][0][
                        "hp"
                    ],
                    "max_level_hp": by_id[
                        f"level-{MAX_CHARACTER_LEVEL:05d}"
                    ]["scenario"]["participants"][0]["hp"],
                },
                "hypothesis": (
                    "O nível não aplica multiplicador direto ao combate; força adicional "
                    "depende de recursos e pontos distribuídos."
                ),
                "recommendation": (
                    "Avaliar builds e conteúdo por faixa com pontos efetivamente alocados "
                    "antes de concluir se a curva de nível é adequada."
                ),
            }
        )
    if {"h11-defense-and-healing", "healing-survival-policy"} <= by_id.keys():
        baseline = observation("h11-defense-and-healing")
        survival = observation("healing-survival-policy")
        findings.append(
            {
                "finding_id": "synthetic-healing-policy-tradeoff",
                "severity": "inconclusive",
                "scope": "synthetic-only",
                "case_refs": [
                    "h11-defense-and-healing",
                    "healing-survival-policy",
                ],
                "sample_sizes": {
                    "h11-defense-and-healing": sample_size(
                        "h11-defense-and-healing"
                    ),
                    "healing-survival-policy": sample_size(
                        "healing-survival-policy"
                    ),
                },
                "facts": {
                    "baseline_result": baseline["result"],
                    "survival_result": survival["result"],
                    "baseline_healing": baseline["party_healing_effective"],
                    "survival_healing": survival["party_healing_effective"],
                    "baseline_party_damage_received": baseline[
                        "party_damage_received_effective"
                    ],
                    "survival_party_damage_received": survival[
                        "party_damage_received_effective"
                    ],
                    "survival_mana": survival["total_mana_consumed"],
                },
                "hypothesis": (
                    "A política de cura pode prolongar a luta e consumir recursos sem "
                    "atingir uma vitória neste cenário."
                ),
                "recommendation": (
                    "Comparar em múltiplos encontros, níveis e composições antes de "
                    "avaliar limiares da política de cura."
                ),
            }
        )
    findings.append(
        {
            "finding_id": "canonical-content-not-assessed",
            "severity": "inconclusive",
            "scope": "canonical-content",
            "case_refs": [],
            "sample_sizes": {},
            "facts": {
                "canonical_entities_loaded": False,
                "reason": (
                    "Não foi encontrado catálogo canônico versionado nos arquivos do "
                    "repositório; banco persistente foi excluído pelo escopo de segurança."
                ),
            },
            "hypothesis": None,
            "recommendation": (
                "Reexecutar com snapshot canônico autorizado e sanitizado em ambiente "
                "isolado."
            ),
        }
    )
    return findings


async def run_analysis(seeds: Iterable[int] = SEEDS) -> dict[str, Any]:
    seed_values = tuple(seeds)
    if not seed_values or len(set(seed_values)) != len(seed_values):
        raise ValueError("Use a non-empty set of unique seeds.")
    cases = []
    for analysis_case in build_analysis_cases():
        batch = await run_batch(
            analysis_case.scenario,
            seed_values,
            party_strategy=analysis_case.party_strategy,
            enemy_strategy=analysis_case.enemy_strategy,
        )
        results = batch["results"]
        observations = [_compact_observation(item) for item in results]
        win_count = sum(item["result"] == "victory" for item in results)
        nominal_wilson = wilson_interval(win_count, len(results)) if results else None
        cases.append(
            {
                "case_id": analysis_case.case_id,
                "family": analysis_case.family,
                "control": analysis_case.control,
                "comparison": analysis_case.comparison,
                "party_strategy": analysis_case.party_strategy,
                "enemy_strategy": analysis_case.enemy_strategy,
                "scenario": scenario_to_dict(analysis_case.scenario),
                "requested": batch["requested"],
                "completed": len(results),
                "failures": batch["failures"],
                "result_counts": batch["aggregate"]["result_counts"],
                "win_rate": batch["aggregate"]["win_rate"],
                "nominal_wilson_95_under_iid_assumption": (
                    list(nominal_wilson) if nominal_wilson else None
                ),
                "inferential_ci_valid": False,
                "inference_note": (
                    "Seeds só determinam IDs de ação neste motor; repetições iguais não "
                    "são trials independentes para inferência estatística."
                ),
                "metrics": {
                    metric: batch["aggregate"][metric]
                    for metric in (
                        "turns",
                        "logical_duration_rounds",
                        "actions_executed",
                        "damage_effective",
                        "healing_effective",
                        "mana_consumed",
                    )
                },
                "side_metrics": {
                    metric: _describe(
                        [item[metric] for item in observations]
                    )
                    for metric in _SUMMARY_METRICS[2:6]
                },
                "participant_metrics": batch["aggregate"]["participant_metrics"],
                "skill_metrics": batch["aggregate"]["skill_metrics"],
                "observations": observations,
            }
        )
    report = {
        "title": "H.12 synthetic combat balance analysis",
        "analysis_version": "1.0.0",
        "simulator_version": SIMULATOR_VERSION,
        "rules_version": RULES_VERSION,
        "confidence_level": CONFIDENCE_LEVEL,
        "progression_rules": {
            "max_character_level": MAX_CHARACTER_LEVEL,
            "base_xp_per_level": BASE_XP_PER_LEVEL,
            "xp_required_for_next_level": "level * base_xp_per_level",
            "hp_per_level": HP_PER_LEVEL,
            "mana_per_level": MANA_PER_LEVEL,
            "attribute_points_per_level": ATTRIBUTE_POINTS_PER_LEVEL,
        },
        "seeds": list(seed_values),
        "seed_count": len(seed_values),
        "scenario_count": len(cases),
        "battle_count_requested": sum(item["requested"] for item in cases),
        "battle_count_completed": sum(item["completed"] for item in cases),
        "failure_count": sum(len(item["failures"]) for item in cases),
        "synthetic_only": True,
        "postgres_accessed": False,
        "cases": cases,
        "paired_comparisons": _comparison_pairs(cases),
        "findings": _build_findings(cases),
        "statistical_method": (
            "H.11 determinístico; estatísticas descritivas são exatas para cada configuração "
            "fixa. Seeds compartilhados permitem rastrear contrastes pareados, mas não "
            "geram incerteza estocástica. Uma execução por configuração é suficiente para "
            "o resultado determinístico; o piloto de 30 seeds verificou estabilidade em "
            "doze configurações. Wilson é exportado apenas como referência nominal sob "
            "hipótese iid, não como intervalo inferencial válido."
        ),
    }
    return report


def export_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def export_csv(report: dict[str, Any]) -> str:
    output = io.StringIO(newline="")
    columns = (
        "case_id",
        "family",
        "scenario_id",
        "seed",
        "simulator_version",
        "rules_version",
        "party_strategy",
        "enemy_strategy",
        "result",
        "turns",
        "logical_duration_rounds",
        "actions_executed",
        "total_damage_effective",
        "total_damage_received_effective",
        "total_healing_effective",
        "total_mana_consumed",
        "players_surviving",
        "enemies_surviving",
        "party_damage_dealt_effective",
        "party_damage_received_effective",
        "enemy_damage_dealt_effective",
        "party_healing_effective",
        "participants_json",
        "skills_json",
    )
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for case in report["cases"]:
        for observation in case["observations"]:
            writer.writerow(
                {
                    "case_id": case["case_id"],
                    "family": case["family"],
                    "scenario_id": case["scenario"]["scenario_id"],
                    "seed": observation["seed"],
                    "simulator_version": report["simulator_version"],
                    "rules_version": report["rules_version"],
                    "party_strategy": case["party_strategy"],
                    "enemy_strategy": case["enemy_strategy"],
                    **{
                        key: observation[key]
                        for key in columns
                        if key in observation
                    },
                    "participants_json": json.dumps(
                        observation["participants"], ensure_ascii=False
                    ),
                    "skills_json": json.dumps(observation["skills"], ensure_ascii=False),
                }
            )
    return output.getvalue()


def export_markdown_summary(report: dict[str, Any]) -> str:
    lines = [
        "# H.12 — Resultados sintéticos reproduzíveis",
        "",
        f"- Cenários: {report['scenario_count']}",
        f"- Batalhas concluídas: {report['battle_count_completed']}/{report['battle_count_requested']}",
        f"- Falhas: {report['failure_count']}",
        f"- Versões: simulador `{report['simulator_version']}`, regras `{report['rules_version']}`",
        "",
        "| Caso | Família | n | Vitórias | Turnos médios | Rodadas médias | Dano efetivo do grupo | Dano recebido pelo grupo | Mana média |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for case in report["cases"]:
        def mean(metric: str) -> str:
            values = [item[metric] for item in case["observations"]]
            return f"{statistics.fmean(values):.2f}" if values else "—"

        wins = case["result_counts"]["victory"]
        lines.append(
            f"| {case['case_id']} | {case['family']} | {case['completed']} | "
            f"{wins} | {mean('turns')} | {mean('logical_duration_rounds')} | "
            f"{mean('total_damage_effective')} | "
            f"{mean('party_damage_received_effective')} | "
            f"{mean('total_mana_consumed')} |"
        )
    lines.extend(
        [
            "",
            "As seeds não acionam aleatoriedade no motor; métricas repetidas são descritivas "
            "das configurações fixas. Não devem ser interpretadas como amostras iid.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run isolated H.12 synthetic balance analysis")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed-start", type=int, default=SEEDS[0])
    parser.add_argument("--seed-count", type=int, default=len(SEEDS))
    arguments = parser.parse_args()
    if arguments.seed_count < 1:
        parser.error("--seed-count must be positive")
    report = asyncio.run(
        run_analysis(range(arguments.seed_start, arguments.seed_start + arguments.seed_count))
    )
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    (arguments.output_dir / "etapa-h12-combat-balance-analysis.json").write_text(
        export_json(report), encoding="utf-8"
    )
    (arguments.output_dir / "etapa-h12-combat-balance-analysis.csv").write_text(
        export_csv(report), encoding="utf-8", newline=""
    )
    (arguments.output_dir / "etapa-h12-combat-balance-analysis-data.md").write_text(
        export_markdown_summary(report), encoding="utf-8"
    )
    if report["failure_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
