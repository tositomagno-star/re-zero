from pydantic import BaseModel, ConfigDict, Field, model_validator


class CombatBalanceMultipliers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hp: float = Field(default=1, ge=0.1, le=5, allow_inf_nan=False)
    attack: float = Field(default=1, ge=0.1, le=5, allow_inf_nan=False)
    defense: float = Field(default=1, ge=0.1, le=5, allow_inf_nan=False)


class CombatBalancePartyRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_count: int = Field(ge=1, le=7)
    enemies: CombatBalanceMultipliers
    bosses: CombatBalanceMultipliers


def default_combat_balance_rules() -> list[CombatBalancePartyRule]:
    return [
        CombatBalancePartyRule(
            player_count=player_count,
            enemies=CombatBalanceMultipliers(),
            bosses=CombatBalanceMultipliers(),
        )
        for player_count in range(1, 8)
    ]


class CombatBalanceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rules: list[CombatBalancePartyRule] = Field(
        default_factory=default_combat_balance_rules,
        min_length=7,
        max_length=7,
    )

    @model_validator(mode="after")
    def validate_party_sizes(self) -> "CombatBalanceSettings":
        if [rule.player_count for rule in self.rules] != list(range(1, 8)):
            raise ValueError("As regras precisam cobrir, em ordem, grupos de 1 a 7 jogadores.")
        return self
