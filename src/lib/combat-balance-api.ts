import { adminContentRequest } from "@/lib/admin-content-api";

export type CombatBalanceMultipliers = {
  hp: number;
  attack: number;
  defense: number;
};

export type CombatBalancePartyRule = {
  player_count: number;
  enemies: CombatBalanceMultipliers;
  bosses: CombatBalanceMultipliers;
};

export type CombatBalanceSettings = {
  rules: CombatBalancePartyRule[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseMultipliers(value: unknown): CombatBalanceMultipliers {
  if (
    !isRecord(value) ||
    typeof value["hp"] !== "number" ||
    typeof value["attack"] !== "number" ||
    typeof value["defense"] !== "number" ||
    ![value["hp"], value["attack"], value["defense"]].every(Number.isFinite)
  ) {
    throw new Error("A API retornou um multiplicador de combate inválido.");
  }
  return {
    hp: value["hp"],
    attack: value["attack"],
    defense: value["defense"],
  };
}

function parseCombatBalanceSettings(value: unknown): CombatBalanceSettings {
  if (!isRecord(value) || !Array.isArray(value["rules"]) || value["rules"].length !== 7) {
    throw new Error("A API retornou regras de balanceamento inválidas.");
  }
  const rules = value["rules"].map((item, index): CombatBalancePartyRule => {
    if (!isRecord(item) || item["player_count"] !== index + 1) {
      throw new Error("A API retornou regras de balanceamento fora de ordem.");
    }
    return {
      player_count: index + 1,
      enemies: parseMultipliers(item["enemies"]),
      bosses: parseMultipliers(item["bosses"]),
    };
  });
  return { rules };
}

export async function getCombatBalanceSettings(): Promise<CombatBalanceSettings> {
  return parseCombatBalanceSettings(await adminContentRequest("/api/admin/combat-balance"));
}

export async function updateCombatBalanceSettings(
  settings: CombatBalanceSettings,
): Promise<CombatBalanceSettings> {
  return parseCombatBalanceSettings(
    await adminContentRequest("/api/admin/combat-balance", "PUT", settings),
  );
}
