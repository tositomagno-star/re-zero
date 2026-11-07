import { apiOrigin } from "@/lib/api-origin";

export type CombatEnemyOption = { id: string; name: string; hp: number };
export type CombatantState = {
  id: string;
  character_id: string | null;
  enemy_id: string | null;
  name: string;
  current_hp: number;
  max_hp: number;
  current_mana: number;
  max_mana: number;
  initiative: number;
  is_active: boolean;
  is_enemy: boolean;
  snapshot: Record<string, unknown>;
  conditions: Record<string, unknown>;
};
export type CombatEvent = {
  sequence: number;
  type: string;
  payload: Record<string, unknown>;
  created_at: string;
};
export type CombatEncounter = {
  id: string;
  title: string;
  status: string;
  version: number;
  active_combatant_id: string | null;
  pending_action?: Record<string, unknown> | null;
  round: number;
  result: string | null;
  reward_status: string | null;
  combatants: CombatantState[];
  events: CombatEvent[];
  last_sequence: number;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function apiError(payload: unknown): string {
  if (isRecord(payload) && typeof payload["detail"] === "string") {
    return payload["detail"];
  }
  if (Array.isArray(payload) && payload.length > 0) {
    const first = payload[0];
    if (isRecord(first) && typeof first["msg"] === "string") return first["msg"];
  }
  return "Não foi possível comunicar com o combate.";
}

async function requestJson(path: string, method = "GET", body?: unknown): Promise<unknown> {
  const response = await fetch(`${apiOrigin}${path}`, {
    method,
    credentials: "include",
    ...(body === undefined
      ? {}
      : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  });
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new Error("A API retornou uma resposta inválida.");
  }
  if (!response.ok) throw new Error(apiError(payload));
  return payload;
}

function parseCombatant(value: unknown): CombatantState {
  if (
    !isRecord(value) ||
    typeof value["id"] !== "string" ||
    !(value["character_id"] === null || typeof value["character_id"] === "string") ||
    !(value["enemy_id"] === null || typeof value["enemy_id"] === "string") ||
    typeof value["name"] !== "string" ||
    typeof value["current_hp"] !== "number" ||
    typeof value["max_hp"] !== "number" ||
    typeof value["current_mana"] !== "number" ||
    typeof value["max_mana"] !== "number" ||
    typeof value["initiative"] !== "number" ||
    typeof value["is_active"] !== "boolean" ||
    typeof value["is_enemy"] !== "boolean" ||
    !isRecord(value["snapshot"]) ||
    !isRecord(value["conditions"])
  ) {
    throw new Error("A API retornou um participante de combate inválido.");
  }
  return value as unknown as CombatantState;
}

function parseEvent(value: unknown): CombatEvent {
  if (
    !isRecord(value) ||
    typeof value["sequence"] !== "number" ||
    typeof value["type"] !== "string" ||
    !isRecord(value["payload"]) ||
    typeof value["created_at"] !== "string"
  ) {
    throw new Error("A API retornou um evento de combate inválido.");
  }
  return value as unknown as CombatEvent;
}

function parseEncounter(value: unknown): CombatEncounter {
  if (
    !isRecord(value) ||
    typeof value["id"] !== "string" ||
    typeof value["title"] !== "string" ||
    typeof value["status"] !== "string" ||
    typeof value["version"] !== "number" ||
    !(value["active_combatant_id"] === null || typeof value["active_combatant_id"] === "string") ||
    typeof value["round"] !== "number" ||
    !(value["result"] === null || typeof value["result"] === "string") ||
    !(value["reward_status"] === null || typeof value["reward_status"] === "string") ||
    !Array.isArray(value["combatants"]) ||
    !Array.isArray(value["events"]) ||
    typeof value["last_sequence"] !== "number"
  ) {
    throw new Error("A API retornou uma batalha em formato inesperado.");
  }
  return {
    ...(value as unknown as CombatEncounter),
    combatants: value["combatants"].map(parseCombatant),
    events: value["events"].map(parseEvent),
  };
}

export async function listCombatEnemies(campaignId: string): Promise<CombatEnemyOption[]> {
  const payload = await requestJson(
    `/api/campaigns/${encodeURIComponent(campaignId)}/combat/enemies`,
  );
  if (!Array.isArray(payload)) throw new Error("A lista de inimigos está inválida.");
  return payload.map((value) => {
    if (
      !isRecord(value) ||
      typeof value["id"] !== "string" ||
      typeof value["name"] !== "string" ||
      typeof value["hp"] !== "number"
    ) {
      throw new Error("A API retornou um inimigo inválido.");
    }
    return { id: value["id"], name: value["name"], hp: value["hp"] };
  });
}

export async function getLatestCombat(
  campaignId: string,
  signal?: AbortSignal,
): Promise<CombatEncounter | null> {
  const response = await fetch(
    `${apiOrigin}/api/campaigns/${encodeURIComponent(campaignId)}/combat`,
    { credentials: "include", ...(signal ? { signal } : {}) },
  );
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new Error("A API retornou uma resposta inválida.");
  }
  if (!response.ok) throw new Error(apiError(payload));
  if (!isRecord(payload) || !(payload["encounter"] === null || isRecord(payload["encounter"]))) {
    throw new Error("A API retornou o estado do combate em formato inesperado.");
  }
  return payload["encounter"] === null ? null : parseEncounter(payload["encounter"]);
}

export async function startCombat(campaignId: string, enemies: string[]): Promise<CombatEncounter> {
  return parseEncounter(
    await requestJson(`/api/campaigns/${encodeURIComponent(campaignId)}/combat`, "POST", {
      enemies,
    }),
  );
}

export async function submitCombatAction(
  campaignId: string,
  encounterId: string,
  input: {
    action_id: string;
    action: "attack" | "skill" | "end_turn";
    target_id?: string;
    skill_id?: string;
  },
): Promise<CombatEncounter> {
  return parseEncounter(
    await requestJson(
      `/api/campaigns/${encodeURIComponent(campaignId)}/combat/${encodeURIComponent(encounterId)}/actions`,
      "POST",
      input,
    ),
  );
}

export async function resolveCombatAction(
  campaignId: string,
  encounterId: string,
  actionId: string,
): Promise<CombatEncounter> {
  return parseEncounter(
    await requestJson(
      `/api/campaigns/${encodeURIComponent(campaignId)}/combat/${encodeURIComponent(encounterId)}/actions/${encodeURIComponent(actionId)}/resolve`,
      "POST",
      {},
    ),
  );
}

export async function getCombatAsset(campaignId: string, assetId: string): Promise<Blob> {
  const response = await fetch(
    `${apiOrigin}/api/campaigns/${encodeURIComponent(campaignId)}/combat/assets/${encodeURIComponent(assetId)}`,
    { credentials: "include" },
  );
  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new Error("Não foi possível carregar a animação da batalha.");
    }
    throw new Error(apiError(payload));
  }
  return response.blob();
}
