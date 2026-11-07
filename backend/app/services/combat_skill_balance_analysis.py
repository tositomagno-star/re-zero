from __future__ import annotations

import argparse
import asyncio
import csv
from dataclasses import dataclass
import io
import json
from pathlib import Path
import statistics
from typing import Any, Iterable

from app.services.combat_simulator import (
    RULES_VERSION,
    SIMULATOR_VERSION,
    BattleScenario,
    CombatantSpec,
    SkillSpec,
    run_batch,
)

SEED = 130
SKILL_CONTEXTS = (
    ("neutral", "Alvo neutro", 60, 8, 8, (), ()),
    ("resistant", "Resistência ao tipo da habilidade", 60, 8, 8, None, ()),
    ("weak", "Fraqueza ao tipo da habilidade", 60, 8, 8, (), None),
    ("high-defense", "Defesa e resistência mágica elevadas", 60, 20, 20, (), ()),
    ("low-hp", "Alvo com pouco HP e risco de overkill", 12, 8, 8, (), ()),
)

STUDY_SKILLS = (
    SkillSpec("Golpe calibrado", "physical", 8, 4, "physical"),
    SkillSpec("Orbe arcano", "magic", 8, 4, "arcane"),
    SkillSpec("Chama controlada", "magic", 8, 4, "fire"),
    SkillSpec(
        "Veneno gradual",
        "special",
        5,
        4,
        "poison",
        additional_effects={
            "effect_type": "damage_over_time",
            "damage_per_turn": 3,
            "duration": 2,
        },
    ),
    SkillSpec("Restauração sintética", "healing", 20, 4, "heal", "ally"),
    SkillSpec("Técnica de mana restrita", "magic", 30, 24, "arcane"),
)

CLASSIFICATIONS = (
    "potencialmente dominante",
    "potencialmente forte",
    "dentro da faixa comparativa",
    "potencialmente fraca",
    "dados insuficientes",
)


@dataclass(frozen=True)
class SkillCase:
    case_id: str
    context_id: str
    context: str
    skill: SkillSpec
    control: BattleScenario
    comparison: BattleScenario
    party_strategy: str = "effective_damage"


@dataclass(frozen=True)
class AiCase:
    case_id: str
    scenario: BattleScenario
    strategies: tuple[str, ...]
    candidates: tuple[SkillSpec, ...]
    expected_eligible_candidates: tuple[str, ...]


def _participants_for_skill(
    skill: SkillSpec | None,
    *,
    enemy_hp: int,
    enemy_defense: int,
    enemy_magic_defense: int,
    resistances: tuple[str, ...],
    weaknesses: tuple[str, ...],
) -> tuple[CombatantSpec, ...]:
    player = CombatantSpec(
        "Combatente sintético",
        "player",
        10,
        200,
        20,
        7,
        magic_attack=12,
        defense=8,
        magic_defense=8,
        speed=6,
        skills=(skill,) if skill is not None else (),
    )
    target = CombatantSpec(
        "Alvo sintético",
        "enemy",
        10,
        enemy_hp,
        0,
        2,
        defense=enemy_defense,
        magic_defense=enemy_magic_defense,
        speed=1,
        resistances=resistances,
        weaknesses=weaknesses,
    )
    return player, target


def build_skill_cases() -> tuple[SkillCase, ...]:
    cases: list[SkillCase] = []
    for skill in STUDY_SKILLS:
        if skill.name == "Restauração sintética":
            continue
        for context_id, context, hp, defense, magic_defense, resistances, weaknesses in SKILL_CONTEXTS:
            selected_resistances = (
                (skill.skill_type,) if resistances is None else resistances
            )
            selected_weaknesses = (
                (skill.skill_type,) if weaknesses is None else weaknesses
            )
            control = BattleScenario(
                f"h13-control-{skill.name.lower().replace(' ', '-')}-{context_id}",
                f"H.13 controle sintético: {skill.name} / {context}",
                _participants_for_skill(
                    None,
                    enemy_hp=hp,
                    enemy_defense=defense,
                    enemy_magic_defense=magic_defense,
                    resistances=selected_resistances,
                    weaknesses=selected_weaknesses,
                ),
                max_turns=80,
            )
            comparison = BattleScenario(
                f"h13-skill-{skill.name.lower().replace(' ', '-')}-{context_id}",
                f"H.13 habilidade sintética: {skill.name} / {context}",
                _participants_for_skill(
                    skill,
                    enemy_hp=hp,
                    enemy_defense=defense,
                    enemy_magic_defense=magic_defense,
                    resistances=selected_resistances,
                    weaknesses=selected_weaknesses,
                ),
                max_turns=80,
            )
            cases.append(
                SkillCase(
                    case_id=f"{skill.name}:{context_id}",
                    context_id=context_id,
                    context=context,
                    skill=skill,
                    control=control,
                    comparison=comparison,
                )
            )
    heal = next(skill for skill in STUDY_SKILLS if skill.name == "Restauração sintética")
    heal_control = (
        CombatantSpec(
            "Curandeiro sintético",
            "player",
            10,
            80,
            20,
            3,
            magic_attack=8,
            speed=8,
        ),
        CombatantSpec(
            "Aliado ferido",
            "player",
            8,
            40,
            0,
            3,
            speed=4,
            current_hp=10,
        ),
    )
    heal_comparison = (
        CombatantSpec(
            "Curandeiro sintético",
            "player",
            10,
            80,
            20,
            3,
            magic_attack=8,
            speed=8,
            skills=(heal,),
        ),
        heal_control[1],
    )
    enemy = CombatantSpec("Ameaça sintética", "enemy", 8, 120, 0, 5, speed=2)
    cases.append(
        SkillCase(
            case_id="Restauração sintética:wounded-ally",
            context_id="wounded-ally",
            context="Aliado começa com 25% de HP",
            skill=heal,
            control=BattleScenario(
                "h13-control-healing-wounded-ally",
                "H.13 controle sintético: cura / aliado ferido",
                (*heal_control, enemy),
                max_turns=40,
            ),
            comparison=BattleScenario(
                "h13-skill-healing-wounded-ally",
                "H.13 habilidade sintética: cura / aliado ferido",
                (*heal_comparison, enemy),
                max_turns=40,
            ),
            party_strategy="survival",
        )
    )
    return tuple(cases)


def build_ai_cases() -> tuple[AiCase, ...]:
    fire = SkillSpec("Explosão de fogo", "magic", 1, 4, "fire")
    arcane = SkillSpec("Projétil arcano", "magic", 20, 4, "arcane")
    enemy = CombatantSpec(
        "Inimigo estrategista",
        "enemy",
        10,
        500,
        20,
        4,
        magic_attack=16,
        speed=8,
        skills=(fire, arcane),
    )
    weak_player = CombatantSpec(
        "Alvo fraco a fogo",
        "player",
        10,
        500,
        0,
        1,
        speed=2,
        weaknesses=("fire",),
    )
    weakness_case = AiCase(
        "enemy-elemental-choice",
        BattleScenario(
            "h13-ai-elemental-choice",
            "H.13 IA: escolha entre dano bruto e fraqueza elemental",
            (weak_player, enemy),
            max_turns=6,
        ),
        ("baseline", "elemental_weakness"),
        (fire, arcane),
        (fire.name, arcane.name),
    )

    cheap = SkillSpec("Feitiço econômico", "magic", 8, 2, "arcane")
    costly = SkillSpec("Feitiço caro", "magic", 8, 8, "arcane")
    mana_enemy = CombatantSpec(
        "Inimigo com orçamento de mana",
        "enemy",
        10,
        500,
        20,
        4,
        magic_attack=12,
        speed=8,
        skills=(cheap, costly),
    )
    mana_case = AiCase(
        "enemy-mana-choice",
        BattleScenario(
            "h13-ai-mana-choice",
            "H.13 IA: habilidades de mesmo dano com custos diferentes",
            (
                CombatantSpec("Alvo durável", "player", 10, 500, 0, 1, speed=2),
                mana_enemy,
            ),
            max_turns=6,
        ),
        ("baseline",),
        (cheap, costly),
        (cheap.name, costly.name),
    )
    return weakness_case, mana_case


def _skill_metric(battle: dict[str, Any], skill_name: str) -> dict[str, Any]:
    metric = battle.get("skills", {}).get(skill_name, {})
    return {
        "uses": int(metric.get("uses", 0)),
        "raw_damage": int(metric.get("raw_damage", 0)),
        "effective_damage": int(metric.get("effective_damage", 0)),
        "healing": int(metric.get("healing", 0)),
        "mana_cost": int(metric.get("mana_cost", 0)),
        "damage_per_use": metric.get("damage_per_use"),
        "damage_per_mana": metric.get("damage_per_mana"),
        "healing_per_mana": metric.get("healing_per_mana"),
        "unique_target_count": int(metric.get("unique_target_count", 0)),
        "effect_application_count": int(metric.get("effect_application_count", 0)),
        "unique_effect_target_count": int(metric.get("unique_effect_target_count", 0)),
        "usage_samples": list(metric.get("usage_samples", [])),
    }


def _first_enemy_skill_choice(battle: dict[str, Any]) -> str | None:
    enemy_ids = {
        str(participant["combatant_id"])
        for participant in battle.get("participants", [])
        if participant.get("side") == "enemy"
    }
    skill_names = {
        str(metric.get("skill_id")): name
        for name, metric in battle.get("skills", {}).items()
        if metric.get("skill_id")
    }
    for event in battle.get("events", []):
        payload = event.get("payload", {})
        if (
            event.get("type") == "action_resolved"
            and str(payload.get("actor_id", "")) in enemy_ids
        ):
            skill_id = payload.get("skill_id")
            return skill_names.get(str(skill_id)) if skill_id else None
    return None


def _paired_context_metrics(
    case: SkillCase,
    control: dict[str, Any],
    comparison: dict[str, Any],
) -> dict[str, Any]:
    control_battle = control["results"][0]
    comparison_battle = comparison["results"][0]
    skill_metrics = _skill_metric(comparison_battle, case.skill.name)
    control_turns = int(control_battle["logical_duration_rounds"])
    comparison_turns = int(comparison_battle["logical_duration_rounds"])
    reduction = (
        (control_turns - comparison_turns) / control_turns
        if control_turns
        else 0.0
    )
    control_players = [
        participant
        for participant in control_battle["participants"]
        if participant["side"] == "player"
    ]
    comparison_players = [
        participant
        for participant in comparison_battle["participants"]
        if participant["side"] == "player"
    ]
    target = next(
        participant
        for participant in comparison_battle["participants"]
        if participant["side"] == "enemy"
    )
    comparison_ally = next(
        (
            participant
            for participant in comparison_players
            if participant["name"] == "Aliado ferido"
        ),
        None,
    )
    control_ally = next(
        (
            participant
            for participant in control_players
            if participant["name"] == "Aliado ferido"
        ),
        None,
    )
    control_party_damage = sum(
        participant["damage_effective"]
        for participant in control_battle["participants"]
        if participant["side"] == "player"
    )
    comparison_party_damage = sum(
        participant["damage_effective"]
        for participant in comparison_battle["participants"]
        if participant["side"] == "player"
    )
    control_survival_rate = sum(item["survived"] for item in control_players) / len(
        control_players
    )
    comparison_survival_rate = sum(
        item["survived"] for item in comparison_players
    ) / len(comparison_players)
    outcome_scores = {"defeat": 0, "turn_limit": 1, "draw": 2, "victory": 3}
    outcome_delta = (
        outcome_scores[comparison_battle["result"]]
        - outcome_scores[control_battle["result"]]
    )
    damage_delta = (
        (comparison_party_damage - control_party_damage)
        / max(1, control_party_damage)
    )
    paired_benefit = outcome_delta > 0 or (
        outcome_delta == 0 and (damage_delta >= 0.10 or reduction >= 0.10)
    )
    paired_disadvantage = outcome_delta < 0 or (
        outcome_delta == 0 and damage_delta <= -0.10 and reduction <= 0.10
    )
    skill_metrics["damage_per_mana"] = (
        None
        if case.skill.skill_type == "heal"
        else skill_metrics["damage_per_mana"]
    )
    skill_metrics["healing_per_mana"] = (
        skill_metrics["healing_per_mana"]
        if case.skill.skill_type == "heal"
        else None
    )
    return {
        "case_id": case.case_id,
        "context_id": case.context_id,
        "context": case.context,
        "skill": case.skill.name,
        "category": case.skill.category,
        "skill_type": case.skill.skill_type,
        "party_strategy": case.party_strategy,
        "mana_cost_per_use": case.skill.mana_cost,
        "effect_type": case.skill.additional_effects.get("effect_type"),
        "control": {
            "result": control_battle["result"],
            "rounds": control_turns,
            "party_damage_effective": control_party_damage,
            "mana_consumed": control_battle["total_mana_consumed"],
            "party_survival_rate": control_survival_rate,
            "wounded_ally_hp_final": (
                control_ally["hp_final"] if control_ally is not None else None
            ),
        },
        "comparison": {
            "result": comparison_battle["result"],
            "rounds": comparison_turns,
            "party_damage_effective": comparison_party_damage,
            "mana_consumed": comparison_battle["total_mana_consumed"],
            "party_survival_rate": comparison_survival_rate,
            "wounded_ally_hp_final": (
                comparison_ally["hp_final"] if comparison_ally is not None else None
            ),
        },
        "round_reduction_fraction": reduction,
        "party_damage_delta_fraction": damage_delta,
        "outcome_improved": outcome_delta > 0,
        "paired_benefit": paired_benefit,
        "paired_disadvantage": paired_disadvantage,
        "party_survival_rate": comparison_survival_rate,
        "wounded_ally_hp_final": (
            comparison_ally["hp_final"] if comparison_ally is not None else None
        ),
        "target_survived": bool(target["survived"]),
        "skill_metrics": skill_metrics,
        "skill_initially_eligible": case.skill.mana_cost <= 20,
        "unavailable_reasons": (
            ["mana insuficiente no início"]
            if case.skill.mana_cost > 20
            else ["motivos de inelegibilidade em turnos posteriores não são registrados pelo motor"]
        ),
        "hit_rate": None,
        "failed_use_count": None,
        "win_contribution": None,
    }


def classify_skill(context_rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(context_rows)
    contexts = {row["context_id"] for row in rows}
    observed_uses = sum(row["skill_metrics"]["uses"] for row in rows)
    positive = sum(row["paired_benefit"] for row in rows)
    worse_outcomes = sum(row["paired_disadvantage"] for row in rows)
    neutral_or_worse = len(rows) - positive
    round_improvements = [row["round_reduction_fraction"] for row in rows]
    if len(contexts) < 3 or observed_uses == 0:
        label = "dados insuficientes"
    elif (
        len(contexts) >= 5
        and observed_uses >= 30
        and positive / len(rows) >= 0.8
        and worse_outcomes == 0
        and statistics.median(round_improvements) >= 0.25
    ):
        label = "potencialmente dominante"
    elif (
        len(contexts) >= 3
        and positive / len(rows) >= 0.6
        and worse_outcomes == 0
        and observed_uses >= 3
    ):
        label = "potencialmente forte"
    elif (
        len(contexts) >= 3
        and observed_uses >= 3
        and neutral_or_worse / len(rows) >= 0.6
        and positive == 0
    ):
        label = "potencialmente fraca"
    elif (
        len(contexts) >= 3
        and all(
            row["control"]["result"] == row["comparison"]["result"]
            and abs(row["party_damage_delta_fraction"]) < 0.10
            and abs(row["round_reduction_fraction"]) < 0.10
            for row in rows
        )
        and worse_outcomes == 0
    ):
        label = "dentro da faixa comparativa"
    else:
        label = "dados insuficientes"
    return {
        "classification": label,
        "confidence": "baixa; evidência exploratória sintética e determinística",
        "sample_basis": {
            "battle_contexts": len(contexts),
            "battles_per_context": 1,
            "observed_uses": observed_uses,
            "independent_random_trials": 0,
        },
        "median_paired_round_reduction_fraction": (
            statistics.median(
                row["round_reduction_fraction"]
                for row in rows
                if row["control"]["result"] == row["comparison"]["result"]
            )
            if any(row["control"]["result"] == row["comparison"]["result"] for row in rows)
            else None
        ),
        "contexts_with_paired_benefit": positive,
        "contexts_with_paired_disadvantage": worse_outcomes,
        "median_paired_damage_delta_fraction": (
            statistics.median(
                row["party_damage_delta_fraction"] for row in rows
            )
            if rows
            else None
        ),
        "canonical_balance_conclusion": "não inferível de dados sintéticos",
    }


def _ai_observation(
    case: AiCase,
    strategy: str,
    battle: dict[str, Any],
) -> dict[str, Any]:
    selected = _first_enemy_skill_choice(battle)
    selected_skill = next(
        (skill for skill in case.candidates if skill.name == selected), None
    )
    unused = [
        skill.name
        for skill in case.candidates
        if skill.name != selected and skill.name in case.expected_eligible_candidates
    ]
    return {
        "case_id": case.case_id,
        "strategy": strategy,
        "first_enemy_action_skill": selected or "ataque básico",
        "first_turn_eligible_skills": list(case.expected_eligible_candidates),
        "eligible_skills_not_selected_first_turn": unused,
        "selected_mana_cost": selected_skill.mana_cost if selected_skill else 0,
        "battle_result": battle["result"],
        "rounds": battle["logical_duration_rounds"],
        "evidence_scope": "decisão observada no primeiro turno inimigo de cenário sintético",
    }


async def run_skill_balance_analysis() -> dict[str, Any]:
    paired_rows: list[dict[str, Any]] = []
    for case in build_skill_cases():
        control = await run_batch(
            case.control, (SEED,), party_strategy=case.party_strategy
        )
        comparison = await run_batch(
            case.comparison, (SEED,), party_strategy=case.party_strategy
        )
        if control["failures"] or comparison["failures"]:
            raise RuntimeError(
                f"Falha de simulação no caso H.13 {case.case_id}: "
                f"{control['failures'] or comparison['failures']}"
            )
        paired_rows.append(_paired_context_metrics(case, control, comparison))

    ai_rows = []
    for case in build_ai_cases():
        for strategy in case.strategies:
            batch = await run_batch(
                case.scenario,
                (SEED,),
                enemy_strategy=strategy,
            )
            if batch["failures"]:
                raise RuntimeError(
                    f"Falha de simulação IA no caso H.13 {case.case_id}: "
                    f"{batch['failures']}"
                )
            ai_rows.append(_ai_observation(case, strategy, batch["results"][0]))
    for case in build_ai_cases():
        case_rows = [row for row in ai_rows if row["case_id"] == case.case_id]
        total_choices = len(case_rows)
        selections = {
            skill.name: sum(
                row["first_enemy_action_skill"] == skill.name for row in case_rows
            )
            for skill in case.candidates
        }
        for row in case_rows:
            row["first_turn_selection_count_by_skill"] = selections
            row["first_turn_selection_frequency_by_skill"] = {
                name: count / total_choices if total_choices else None
                for name, count in selections.items()
            }

    skill_assessments = []
    for skill in STUDY_SKILLS:
        rows = [row for row in paired_rows if row["skill"] == skill.name]
        skill_assessments.append(
            {
                "skill": skill.name,
                "category": skill.category,
                "skill_type": skill.skill_type,
                "effect_type": (
                    "healing"
                    if skill.skill_type == "heal"
                    else skill.additional_effects.get("effect_type", "dano direto")
                ),
                "mana_cost": skill.mana_cost,
                "classification": classify_skill(rows),
                "metrics": {
                    "uses": sum(row["skill_metrics"]["uses"] for row in rows),
                    "raw_damage": sum(
                        row["skill_metrics"]["raw_damage"] for row in rows
                    ),
                    "effective_direct_damage": sum(
                        row["skill_metrics"]["effective_damage"] for row in rows
                    ),
                    "effective_damage_median_per_use": _median(
                        sample["effective_damage"]
                        for row in rows
                        for sample in row["skill_metrics"]["usage_samples"]
                    )
                    if skill.skill_type != "heal"
                    else None,
                    "effective_damage_mean_per_use": _mean(
                        sample["effective_damage"]
                        for row in rows
                        for sample in row["skill_metrics"]["usage_samples"]
                    )
                    if skill.skill_type != "heal"
                    else None,
                    "damage_per_mana": (
                        None
                        if skill.skill_type == "heal"
                        else _ratio(
                            sum(
                                row["skill_metrics"]["effective_damage"]
                                for row in rows
                            ),
                            sum(row["skill_metrics"]["mana_cost"] for row in rows),
                        )
                    ),
                    "effective_direct_damage_per_combat_turn": _ratio(
                        sum(row["skill_metrics"]["effective_damage"] for row in rows),
                        sum(row["comparison"]["rounds"] for row in rows),
                    )
                    if skill.skill_type != "heal"
                    else None,
                    "healing": sum(row["skill_metrics"]["healing"] for row in rows),
                    "healing_mean_per_use": (
                        _ratio(
                            sum(row["skill_metrics"]["healing"] for row in rows),
                            sum(row["skill_metrics"]["uses"] for row in rows),
                        )
                        if skill.skill_type == "heal"
                        else None
                    ),
                    "healing_per_mana": (
                        _ratio(
                            sum(row["skill_metrics"]["healing"] for row in rows),
                            sum(row["skill_metrics"]["mana_cost"] for row in rows),
                        )
                        if skill.skill_type == "heal"
                        else None
                    ),
                    "mana_cost": sum(
                        row["skill_metrics"]["mana_cost"] for row in rows
                    ),
                    "mean_mana_cost_per_use": _ratio(
                        sum(row["skill_metrics"]["mana_cost"] for row in rows),
                        sum(row["skill_metrics"]["uses"] for row in rows),
                    ),
                    "effect_applications": sum(
                        row["skill_metrics"]["effect_application_count"]
                        for row in rows
                    ),
                    "unique_targets_per_battle_total": sum(
                        row["skill_metrics"]["unique_target_count"] for row in rows
                    ),
                    "contexts": len({row["context_id"] for row in rows}),
                    "hit_rate": None,
                    "failed_use_count": None,
                    "win_contribution": None,
                    "damage_over_time_attribution": (
                        None
                        if skill.additional_effects.get("effect_type")
                        == "damage_over_time"
                        else "não aplicável"
                    ),
                },
                "comparisons": rows,
            }
        )

    ai_baseline_elemental = next(
        row
        for row in ai_rows
        if row["case_id"] == "enemy-elemental-choice"
        and row["strategy"] == "baseline"
    )
    ai_weakness_elemental = next(
        row
        for row in ai_rows
        if row["case_id"] == "enemy-elemental-choice"
        and row["strategy"] == "elemental_weakness"
    )
    ai_mana = next(row for row in ai_rows if row["case_id"] == "enemy-mana-choice")
    paired_benefits = sum(row["paired_benefit"] for row in paired_rows)
    effect_applications = sum(
        row["skill_metrics"]["effect_application_count"] for row in paired_rows
    )
    healing_total = sum(row["skill_metrics"]["healing"] for row in paired_rows)

    return {
        "stage": "H.13",
        "source": "synthetic-only",
        "canonical_catalog_accessed": False,
        "seed": SEED,
        "simulator_version": SIMULATOR_VERSION,
        "rules_version": RULES_VERSION,
        "methodology": {
            "engine": "H.4/H.7 authoritative resolvers through H.11 run_batch",
            "storage": "SQLite :memory: isolated per batch",
            "paired_control": (
                "mesmo nível, atributos, equipamento (nenhum), HP/mana iniciais, "
                "alvo, composição, estratégia e seed; somente habilidade difere"
            ),
            "randomness": (
                "o motor não usa RNG; seed reproduz IDs, não cria observações independentes"
            ),
            "classification_thresholds": {
                "potentially_dominant": (
                    "provisório: pelo menos 5 contextos, 30 usos observados, "
                    "redução mediana de turnos >=25%, benefício em >=80% dos "
                    "contextos pareados e nenhum contexto pior"
                ),
                "potentially_strong": (
                    "provisório: pelo menos 3 contextos, benefício em >=60% e "
                    "nenhum contexto pior"
                ),
                "potentially_weak": (
                    "provisório: pelo menos 3 contextos e 3 usos, benefício pareado "
                    "inferior a 10% em >=60% dos casos e nenhum benefício >=10%"
                ),
                "within_range": (
                    "provisório: pelo menos 3 contextos, resultados iguais e variações "
                    "de dano e rodadas inferiores a 10% em todos"
                ),
                "insufficient": "demais situações ou habilidade sem uso observado",
            },
        },
        "metric_limitations": [
            "O motor não modela acerto, erro, precisão, evasão ou críticos; taxa de acerto não se aplica.",
            "Tentativas rejeitadas e motivos de inelegibilidade durante turnos posteriores não são persistidos nos eventos do simulador.",
            "Dano contínuo é registrado como efeito do alvo sem atribuição confiável ao conjurador; não é creditado ao dano efetivo direto da habilidade.",
            "Contribuição causal de vitória por habilidade não é uma métrica do motor; o contraste pareado de resultado/turnos é apenas evidência exploratória.",
            "Alvos por uso contam alvos diretos de ação; alvos dos efeitos são informados separadamente.",
            "A habilidade selecionada pode ser impedida por custo, cooldown, alcance, alvo inválido ou estratégia; só a insuficiência inicial de mana e elegibilidade do primeiro turno nos casos definidos são inferíveis.",
        ],
        "skills": skill_assessments,
        "comparisons": paired_rows,
        "ai_observations": ai_rows,
        "conclusions": {
            "synthetic_observations": [
                (
                    f"{paired_benefits} de {len(paired_rows)} contrastes mostraram "
                    "benefício pareado (resultado melhor, ou mesmo resultado com "
                    "mais dano efetivo ou menos rodadas); são observações determinísticas."
                ),
                (
                    f"Foram observadas {effect_applications} aplicações de efeitos "
                    f"e {healing_total} pontos de cura efetiva no conjunto sintético."
                ),
                (
                    f"Na escolha elemental, baseline selecionou "
                    f"{ai_baseline_elemental['first_enemy_action_skill']} e "
                    f"elemental_weakness selecionou "
                    f"{ai_weakness_elemental['first_enemy_action_skill']}."
                ),
                (
                    "No cenário de custo, baseline selecionou "
                    f"{ai_mana['first_enemy_action_skill']} entre habilidades sintéticas "
                    "de mesmo dano e custos diferentes."
                ),
                "As métricas não permitem inferir uso real nem balanceamento do catálogo canônico.",
            ],
            "hypotheses": [
                "Fraquezas, resistências, defesa e HP do alvo alteram eficiência direta e podem alterar a escolha da IA.",
                "A eficiência observada de efeitos contínuos é subestimada no dano por mana por falta de atribuição de ticks no motor.",
            ],
            "canonical_conclusions": (
                "Nenhuma habilidade canônica pode ser classificada: o catálogo canônico não foi lido."
            ),
        },
    }


def _median(values: Iterable[int]) -> float | None:
    values = list(values)
    return float(statistics.median(values)) if values else None


def _mean(values: Iterable[int]) -> float | None:
    values = list(values)
    return statistics.fmean(values) if values else None


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def report_to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Etapa H.13 — Identificação de habilidades dominantes e fracas",
        "",
        "**Escopo:** exclusivamente sintético; não representa o catálogo canônico. "
        "Nenhuma regra de combate foi alterada.",
        "",
        "## Resumo",
        "",
        f"- Habilidades sintéticas avaliadas: **{len(report['skills'])}**.",
        f"- Comparações pareadas por contexto: **{len(report['comparisons'])}**.",
        f"- Decisões de IA registradas: **{len(report['ai_observations'])}**.",
        f"- Seed: `{report['seed']}`; o motor é determinístico e não usa RNG.",
        "- Cada comparação é uma batalha pareada por cenário e seed; repetir seeds não aumenta a evidência independente.",
        "- Nenhuma conclusão de balanceamento canônico foi feita.",
        "",
        "## Classificações exploratórias",
        "",
        "| Habilidade sintética | Tipo | Usos | Dano efetivo direto | Dano direto/mana | Dano direto/turno | Custo médio de mana/uso | Efeitos | Contextos | Classificação |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for skill in report["skills"]:
        metrics = skill["metrics"]
        lines.append(
            f"| {skill['skill']} | {skill['category']} / {skill['skill_type']} | "
            f"{metrics['uses']} | {metrics['effective_direct_damage']} | "
            f"{_format(metric=metrics['damage_per_mana'])} | "
            f"{_format(metric=metrics['effective_direct_damage_per_combat_turn'])} | "
            f"{_format(metric=metrics['mean_mana_cost_per_use'])} | "
            f"{metrics['effect_applications']} | {metrics['contexts']} | "
            f"{skill['classification']['classification']} |"
        )
    lines.extend(
        [
            "",
            "Todas as classificações são provisórias e referem-se somente aos "
            "contrastes sintéticos testados. As amostras determinísticas não sustentam "
            "inferência estatística nem conclusões sobre habilidades publicadas.",
            "",
            "## Comparações por contexto",
            "",
            "| Habilidade | Contexto | Usos | Dano efetivo direto | Dano/mana | Efeitos aplicados | Rodadas controle → habilidade | Delta de rodadas | Resultado controle → habilidade | Sobrevivência do grupo (controle → habilidade) |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|---:|",
        ]
    )
    for row in report["comparisons"]:
        metrics = row["skill_metrics"]
        lines.append(
            f"| {row['skill']} | {row['context']} | {metrics['uses']} | "
            f"{metrics['effective_damage']} | {_format(metric=metrics['damage_per_mana'])} | "
            f"{metrics['effect_application_count']} | "
            f"{row['control']['rounds']} → {row['comparison']['rounds']} | "
            f"{row['round_reduction_fraction']:+.1%} | "
            f"{row['control']['result']} → {row['comparison']['result']} | "
            f"{row['control']['party_survival_rate']:.0%} → "
            f"{row['comparison']['party_survival_rate']:.0%} |"
        )
    lines.extend(
        [
            "",
            "## Escolhas da IA",
            "",
            "| Caso sintético | Estratégia | Primeira habilidade escolhida | Frequência de escolha no caso | Candidatas elegíveis no primeiro turno | Elegíveis não escolhidas |",
            "|---|---|---|---|---|---|",
        ]
    )
    for observation in report["ai_observations"]:
        frequencies = ", ".join(
            f"{name}: {frequency:.0%}"
            for name, frequency in observation[
                "first_turn_selection_frequency_by_skill"
            ].items()
        )
        lines.append(
            f"| {observation['case_id']} | {observation['strategy']} | "
            f"{observation['first_enemy_action_skill']} | "
            f"{frequencies} | "
            f"{', '.join(observation['first_turn_eligible_skills'])} | "
            f"{', '.join(observation['eligible_skills_not_selected_first_turn']) or 'nenhuma'} |"
        )
    lines.extend(
        [
            "",
            "## Limitações",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["metric_limitations"])
    lines.extend(
        [
            "- Não foram acessados PostgreSQL, `cronicas_do_reino_dev` ou `cronicas_do_reino_test`.",
            "- Não foram executadas migrations, nem alterados dados persistentes ou regras canônicas.",
            "- Os nomes e atributos deste estudo são sintéticos; ausência de catálogo canônico impede conclusões sobre conteúdo real.",
            "",
            "## Fatos observados, hipóteses e conclusões",
            "",
            "### Fatos nos testes sintéticos",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["conclusions"]["synthetic_observations"])
    lines.extend(["", "### Hipóteses para investigação", ""])
    lines.extend(f"- {item}" for item in report["conclusions"]["hypotheses"])
    lines.extend(
        [
            "",
            "### Conclusão canônica",
            "",
            report["conclusions"]["canonical_conclusions"],
        ]
    )
    lines.extend(
        [
            "",
            "### Critérios provisórios",
            "",
        ]
    )
    lines.extend(
        f"- **{label}:** {criterion}"
        for label, criterion in report["methodology"]["classification_thresholds"].items()
    )
    lines.extend(
        [
            "",
            "Os limiares são critérios experimentais para explorar estes dados "
            "sintéticos, não regras oficiais. A contagem de usos descreve ações "
            "observadas, não ensaios estatísticos independentes. Benefício pareado "
            "significa resultado melhor; ou, com o mesmo resultado, dano efetivo "
            "do grupo ou rodadas melhores em pelo menos 10%.",
            "",
            "## Artefatos",
            "",
            "Os dados completos estão em `etapa-h13-skill-balance-analysis.json` e as linhas comparáveis em `etapa-h13-skill-balance-analysis.csv`.",
            "",
        ]
    )
    return "\n".join(lines)


def report_to_csv(report: dict[str, Any]) -> str:
    output = io.StringIO(newline="")
    columns = (
        "skill",
        "category",
        "skill_type",
        "context_id",
        "context",
        "battle_count",
        "uses",
        "raw_damage",
        "effective_direct_damage",
        "mean_effective_damage_per_use",
        "median_effective_damage_per_use",
        "mean_mana_cost_per_use",
        "mana_cost",
        "damage_per_mana",
        "healing_per_mana",
        "effective_direct_damage_per_combat_turn",
        "healing",
        "effect_applications",
        "direct_target_count",
        "hit_rate",
        "failed_use_count",
        "control_rounds",
        "skill_rounds",
        "round_reduction_fraction",
        "paired_benefit",
        "control_party_survival_rate",
        "skill_party_survival_rate",
        "wounded_ally_hp_final",
        "control_result",
        "skill_result",
        "classification",
    )
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    classifications = {
        item["skill"]: item["classification"]["classification"]
        for item in report["skills"]
    }
    for row in report["comparisons"]:
        metric = row["skill_metrics"]
        writer.writerow(
            {
                "skill": row["skill"],
                "category": row["category"],
                "skill_type": row["skill_type"],
                "context_id": row["context_id"],
                "context": row["context"],
                "battle_count": 1,
                "uses": metric["uses"],
                "raw_damage": metric["raw_damage"],
                "effective_direct_damage": metric["effective_damage"],
                "mean_effective_damage_per_use": _mean(
                    sample["effective_damage"] for sample in metric["usage_samples"]
                ),
                "median_effective_damage_per_use": _median(
                    sample["effective_damage"] for sample in metric["usage_samples"]
                ),
                "mean_mana_cost_per_use": _ratio(
                    metric["mana_cost"], metric["uses"]
                ),
                "mana_cost": metric["mana_cost"],
                "damage_per_mana": metric["damage_per_mana"],
                "healing_per_mana": metric["healing_per_mana"],
                "effective_direct_damage_per_combat_turn": _ratio(
                    metric["effective_damage"], row["comparison"]["rounds"]
                ),
                "healing": metric["healing"],
                "effect_applications": metric["effect_application_count"],
                "direct_target_count": metric["unique_target_count"],
                "hit_rate": "",
                "failed_use_count": "",
                "control_rounds": row["control"]["rounds"],
                "skill_rounds": row["comparison"]["rounds"],
                "round_reduction_fraction": row["round_reduction_fraction"],
                "paired_benefit": row["paired_benefit"],
                "control_party_survival_rate": row["control"]["party_survival_rate"],
                "skill_party_survival_rate": row["comparison"]["party_survival_rate"],
                "wounded_ally_hp_final": row["comparison"]["wounded_ally_hp_final"],
                "control_result": row["control"]["result"],
                "skill_result": row["comparison"]["result"],
                "classification": classifications[row["skill"]],
            }
        )
    return output.getvalue()


def write_reports(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "etapa-h13-skill-balance-analysis.json"
    csv_path = output_dir / "etapa-h13-skill-balance-analysis.csv"
    markdown_path = output_dir / "etapa-h13-skill-balance-analysis.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    csv_path.write_text(report_to_csv(report), encoding="utf-8", newline="")
    markdown_path.write_text(report_to_markdown(report), encoding="utf-8")
    return markdown_path, json_path, csv_path


def _format(*, metric: float | None) -> str:
    return "n/d" if metric is None else f"{metric:.2f}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera a análise sintética de habilidades H.13."
    )
    parser.add_argument("--output-dir", type=Path, default=Path("docs"))
    arguments = parser.parse_args()
    report = asyncio.run(run_skill_balance_analysis())
    paths = write_reports(report, arguments.output_dir)
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
