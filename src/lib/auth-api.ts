import { apiOrigin } from "@/lib/api-origin";

export interface AuthUser {
  id: string;
  username: string;
  display_name: string;
}

export interface CampaignMember {
  user_id: string;
  username: string;
  display_name: string;
  role: string;
  is_ready: boolean;
  is_connected: boolean;
  character_id: string | null;
  character_name: string | null;
  level: number | null;
  hp: number | null;
  max_hp: number | null;
  mana: number | null;
  max_mana: number | null;
}

export interface CampaignSummary {
  id: string;
  title: string;
  description: string;
  join_code: string;
  status: string;
  owner_id: string;
  owner_display_name: string;
  min_players: number;
  max_players: number;
  participant_count: number;
  available_slots: number;
  current_chapter_id: string | null;
  current_node_id: string | null;
  last_activity_at: string;
  membership_status: string;
  is_owner: boolean;
  solo: boolean;
}

export interface Campaign extends CampaignSummary {
  members: CampaignMember[];
}

export interface SoloCharacter {
  id: string;
  name: string;
  character_class: string | null;
  ancestry: string | null;
  level: number;
  hp: number;
  max_hp: number;
  active: boolean;
}

export interface CharacterSheetItem {
  item_id: string;
  name: string;
  description: string;
  category: string;
  is_career: boolean;
  rarity: string;
  image_url: string | null;
  weight: number;
  effects: Record<string, unknown>;
  quantity: number;
  is_equipped: boolean;
  slot: string | null;
  origin: Record<string, unknown>;
}

export interface CharacterSheetSkill {
  id: string;
  name: string;
  category: string;
  description: string;
  mana_cost: number;
  effects: Record<string, unknown>;
  target: string;
  cooldown_seconds: number;
  origin: Record<string, unknown>;
}

export interface CharacterSheetQuest {
  id: string;
  title: string;
  description: string;
  status: string;
  progress: Record<string, unknown>;
  objectives: CharacterQuestObjective[];
  rewards: Record<string, unknown>;
}

export interface CharacterQuestObjective {
  id: string;
  title: string;
  description: string;
  target: number;
}

export type CampaignQuest = CharacterSheetQuest;

function parseQuestObjective(value: unknown): CharacterQuestObjective {
  if (
    !isRecord(value) ||
    !isString(value["id"]) ||
    !isString(value["title"]) ||
    !isString(value["description"]) ||
    !isNumber(value["target"])
  ) {
    throw new Error("A API retornou um objetivo de missão em formato inesperado.");
  }
  return {
    id: value["id"],
    title: value["title"],
    description: value["description"],
    target: value["target"],
  };
}

export interface CharacterProgressionEvent {
  id: string;
  created_at: string;
  source_type: string;
  source_id: string | null;
  source_name: string | null;
  xp_awarded: number;
  xp_before: number;
  xp_after: number;
  level_before: number;
  level_after: number;
  gold_awarded: number;
  attribute_points_awarded: number;
  max_hp_increase: number;
  max_mana_increase: number;
  items: CharacterProgressionItem[];
}

export interface CharacterProgressionItem {
  item_id: string;
  name: string;
  quantity: number;
}

export interface CharacterSheet {
  name: string;
  description: string;
  character_class: string | null;
  ancestry: string | null;
  level: number;
  xp: number;
  xp_to_next_level: number | null;
  xp_progress_percent: number;
  attribute_points: number;
  gold: number;
  hp: number;
  max_hp: number;
  mana: number;
  max_mana: number;
  attributes: Record<string, unknown>;
  inventory: CharacterSheetItem[];
  skills: CharacterSheetSkill[];
  quests: CharacterSheetQuest[];
  progression_history: CharacterProgressionEvent[];
}

export interface NarrativeChoice {
  id: string;
  label: string;
  position: number;
  next_node_id: string | null;
  conditions: Record<string, unknown>;
  consequences: Record<string, unknown>;
}

export interface NarrativeVoteTally {
  choice_id: string;
  label: string;
  votes: number;
}

export interface NarrativeVote {
  status: string;
  round_number: number;
  deadline_at: string | null;
  allow_vote_change: boolean;
  eligible_count: number;
  voted_count: number;
  my_choice_id: string | null;
  tally: NarrativeVoteTally[];
  result: Record<string, unknown> | null;
}

export interface NarrativeEvent {
  sequence_number: number;
  actor_user_id: string | null;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface NarrativeGame {
  session_id: string;
  status: string;
  chapter: {
    id: string;
    title: string;
    summary: string;
    narrative: string;
  };
  scene: {
    id: string;
    title: string;
    narrative: string;
    choices: NarrativeChoice[];
  };
  participants: CampaignMember[];
  vote: NarrativeVote | null;
  last_result: Record<string, unknown> | null;
  history: NarrativeEvent[];
}

export class AuthApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "AuthApiError";
  }
}

async function requestJson(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
  method?: "GET" | "POST" | "PUT" | "DELETE",
): Promise<unknown> {
  const request: RequestInit = {
    method: method ?? (body === undefined ? "GET" : "POST"),
    credentials: "include",
    ...(signal ? { signal } : {}),
  };
  if (body !== undefined) {
    request.headers = { "Content-Type": "application/json" };
    request.body = JSON.stringify(body);
  }
  const response = await fetch(`${apiOrigin}${path}`, request);

  if (response.status === 204) {
    return undefined;
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new AuthApiError("A API retornou uma resposta inválida.", response.status);
  }

  if (!response.ok) {
    throw new AuthApiError(responseErrorMessage(payload), response.status);
  }

  return payload;
}

function parseUser(payload: unknown): AuthUser {
  if (
    typeof payload !== "object" ||
    payload === null ||
    !("id" in payload) ||
    !("username" in payload) ||
    !("display_name" in payload) ||
    typeof payload.id !== "string" ||
    typeof payload.username !== "string" ||
    typeof payload.display_name !== "string"
  ) {
    throw new Error("A API retornou os dados da conta em um formato inesperado.");
  }
  return {
    id: payload.id,
    username: payload.username,
    display_name: payload.display_name,
  };
}

function isRecord(payload: unknown): payload is Record<string, unknown> {
  return typeof payload === "object" && payload !== null;
}

function responseErrorMessage(payload: unknown): string {
  if (!isRecord(payload)) return "Verifique os dados e tente novamente.";
  const detail = payload["detail"];
  if (isString(detail)) return detail;
  if (Array.isArray(detail)) {
    const firstError = detail[0];
    if (isRecord(firstError) && isString(firstError["msg"])) {
      return firstError["msg"];
    }
  }
  return "Verifique os dados e tente novamente.";
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isNullableString(value: unknown): value is string | null {
  return value === null || isString(value);
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || isNumber(value);
}

function parseCampaignSummary(payload: unknown): CampaignSummary {
  if (
    !isRecord(payload) ||
    !isString(payload["id"]) ||
    !isString(payload["title"]) ||
    !isString(payload["description"]) ||
    !isString(payload["join_code"]) ||
    !isString(payload["status"]) ||
    !isString(payload["owner_id"]) ||
    !isString(payload["owner_display_name"]) ||
    !isNumber(payload["min_players"]) ||
    !isNumber(payload["max_players"]) ||
    !isNumber(payload["participant_count"]) ||
    !isNumber(payload["available_slots"]) ||
    !isNullableString(payload["current_chapter_id"]) ||
    !isNullableString(payload["current_node_id"]) ||
    !isString(payload["last_activity_at"]) ||
    !isString(payload["membership_status"]) ||
    typeof payload["is_owner"] !== "boolean"
  ) {
    throw new Error("A API retornou os dados da campanha em um formato inesperado.");
  }
  return {
    id: payload["id"],
    title: payload["title"],
    description: payload["description"],
    join_code: payload["join_code"],
    status: payload["status"],
    owner_id: payload["owner_id"],
    owner_display_name: payload["owner_display_name"],
    min_players: payload["min_players"],
    max_players: payload["max_players"],
    participant_count: payload["participant_count"],
    available_slots: payload["available_slots"],
    current_chapter_id: payload["current_chapter_id"],
    current_node_id: payload["current_node_id"],
    last_activity_at: payload["last_activity_at"],
    membership_status: payload["membership_status"],
    is_owner: payload["is_owner"],
    solo: typeof payload["solo"] === "boolean" ? payload["solo"] : payload["max_players"] === 1,
  };
}

function parseCampaignMember(payload: unknown): CampaignMember {
  if (
    !isRecord(payload) ||
    !isString(payload["user_id"]) ||
    !isString(payload["username"]) ||
    !isString(payload["display_name"]) ||
    !isString(payload["role"]) ||
    typeof payload["is_ready"] !== "boolean" ||
    typeof payload["is_connected"] !== "boolean" ||
    !isNullableString(payload["character_id"]) ||
    !isNullableString(payload["character_name"]) ||
    !isNullableNumber(payload["level"]) ||
    !isNullableNumber(payload["hp"]) ||
    !isNullableNumber(payload["max_hp"]) ||
    !isNullableNumber(payload["mana"]) ||
    !isNullableNumber(payload["max_mana"])
  ) {
    throw new Error("A API retornou os dados de um participante em um formato inesperado.");
  }
  return {
    user_id: payload["user_id"],
    username: payload["username"],
    display_name: payload["display_name"],
    role: payload["role"],
    is_ready: payload["is_ready"],
    is_connected: payload["is_connected"],
    character_id: payload["character_id"],
    character_name: payload["character_name"],
    level: payload["level"],
    hp: payload["hp"],
    max_hp: payload["max_hp"],
    mana: payload["mana"],
    max_mana: payload["max_mana"],
  };
}

function parseCampaign(payload: unknown): Campaign {
  const summary = parseCampaignSummary(payload);
  if (!isRecord(payload) || !Array.isArray(payload["members"])) {
    throw new Error("A API retornou o lobby em um formato inesperado.");
  }
  return {
    ...summary,
    members: payload["members"].map(parseCampaignMember),
  };
}

function parseCharacterSheet(payload: unknown): CharacterSheet {
  const progressionHistory =
    isRecord(payload) && Array.isArray(payload["progression_history"])
      ? payload["progression_history"].map((entry): CharacterProgressionEvent => {
          if (
            !isRecord(entry) ||
            !isString(entry["id"]) ||
            !isString(entry["created_at"]) ||
            !isString(entry["source_type"]) ||
            !(entry["source_id"] === undefined || isNullableString(entry["source_id"])) ||
            !(entry["source_name"] === undefined || isNullableString(entry["source_name"])) ||
            !isNumber(entry["xp_awarded"]) ||
            !isNumber(entry["xp_before"]) ||
            !isNumber(entry["xp_after"]) ||
            !isNumber(entry["level_before"]) ||
            !isNumber(entry["level_after"]) ||
            !isNumber(entry["gold_awarded"]) ||
            !isNumber(entry["attribute_points_awarded"]) ||
            !isNumber(entry["max_hp_increase"]) ||
            !isNumber(entry["max_mana_increase"]) ||
            !Array.isArray(entry["items"])
          ) {
            throw new Error("A API retornou um evento de evolução em formato inesperado.");
          }
          return {
            id: entry["id"],
            created_at: entry["created_at"],
            source_type: entry["source_type"],
            source_id: isString(entry["source_id"]) ? entry["source_id"] : null,
            source_name: isString(entry["source_name"]) ? entry["source_name"] : null,
            xp_awarded: entry["xp_awarded"],
            xp_before: entry["xp_before"],
            xp_after: entry["xp_after"],
            level_before: entry["level_before"],
            level_after: entry["level_after"],
            gold_awarded: entry["gold_awarded"],
            attribute_points_awarded: entry["attribute_points_awarded"],
            max_hp_increase: entry["max_hp_increase"],
            max_mana_increase: entry["max_mana_increase"],
            items: entry["items"].map((item): CharacterProgressionItem => {
              if (
                !isRecord(item) ||
                !isString(item["item_id"]) ||
                !isString(item["name"]) ||
                !isNumber(item["quantity"])
              ) {
                throw new Error("A API retornou um item de recompensa inválido.");
              }
              return {
                item_id: item["item_id"],
                name: item["name"],
                quantity: item["quantity"],
              };
            }),
          };
        })
      : null;
  if (
    !isRecord(payload) ||
    !isString(payload["name"]) ||
    !isString(payload["description"]) ||
    !isNullableString(payload["character_class"]) ||
    !isNullableString(payload["ancestry"]) ||
    !isNumber(payload["level"]) ||
    !isNumber(payload["xp"]) ||
    !(payload["xp_to_next_level"] === null || isNumber(payload["xp_to_next_level"])) ||
    !isNumber(payload["xp_progress_percent"]) ||
    !isNumber(payload["attribute_points"]) ||
    !isNumber(payload["gold"]) ||
    !isNumber(payload["hp"]) ||
    !isNumber(payload["max_hp"]) ||
    !isNumber(payload["mana"]) ||
    !isNumber(payload["max_mana"]) ||
    !isRecord(payload["attributes"]) ||
    !Array.isArray(payload["inventory"]) ||
    !Array.isArray(payload["skills"]) ||
    !Array.isArray(payload["quests"]) ||
    progressionHistory === null
  ) {
    throw new Error("A API retornou a ficha do personagem em um formato inesperado.");
  }
  const inventory = payload["inventory"].map((item): CharacterSheetItem => {
    if (
      !isRecord(item) ||
      !isString(item["item_id"]) ||
      !isString(item["name"]) ||
      !isString(item["description"]) ||
      !isString(item["category"]) ||
      !isString(item["rarity"]) ||
      !isNullableString(item["image_url"]) ||
      !isNumber(item["weight"]) ||
      !isRecord(item["effects"]) ||
      !isNumber(item["quantity"]) ||
      typeof item["is_equipped"] !== "boolean" ||
      !isNullableString(item["slot"]) ||
      !isRecord(item["origin"] ?? {})
    ) {
      throw new Error("A API retornou um item da ficha em um formato inesperado.");
    }
    return {
      item_id: item["item_id"],
      name: item["name"],
      description: item["description"],
      category: item["category"],
      is_career:
        typeof item["is_career"] === "boolean"
          ? item["is_career"]
          : item["category"].toLowerCase() === "carreira",
      rarity: item["rarity"],
      image_url: item["image_url"],
      weight: item["weight"],
      effects: item["effects"],
      quantity: item["quantity"],
      is_equipped: item["is_equipped"],
      slot: item["slot"],
      origin: isRecord(item["origin"]) ? item["origin"] : {},
    };
  });
  const skills = payload["skills"].map((skill): CharacterSheetSkill => {
    if (
      !isRecord(skill) ||
      !isString(skill["id"]) ||
      !isString(skill["name"]) ||
      !isString(skill["category"]) ||
      !isString(skill["description"]) ||
      !isNumber(skill["mana_cost"]) ||
      !isRecord(skill["effects"]) ||
      !isString(skill["target"]) ||
      !isNumber(skill["cooldown_seconds"]) ||
      !isRecord(skill["origin"] ?? {})
    ) {
      throw new Error("A API retornou uma habilidade da ficha em um formato inesperado.");
    }
    return {
      id: skill["id"],
      name: skill["name"],
      category: skill["category"],
      description: skill["description"],
      mana_cost: skill["mana_cost"],
      effects: skill["effects"],
      target: skill["target"],
      cooldown_seconds: skill["cooldown_seconds"],
      origin: isRecord(skill["origin"]) ? skill["origin"] : {},
    };
  });
  const quests = payload["quests"].map((quest): CharacterSheetQuest => {
    if (
      !isRecord(quest) ||
      !isString(quest["id"]) ||
      !isString(quest["title"]) ||
      !isString(quest["description"]) ||
      !isString(quest["status"]) ||
      !isRecord(quest["progress"]) ||
      (quest["objectives"] !== undefined && !Array.isArray(quest["objectives"])) ||
      (quest["rewards"] !== undefined && !isRecord(quest["rewards"]))
    ) {
      throw new Error("A API retornou uma missão da ficha em um formato inesperado.");
    }
    return {
      id: quest["id"],
      title: quest["title"],
      description: quest["description"],
      status: quest["status"],
      progress: quest["progress"],
      objectives: Array.isArray(quest["objectives"])
        ? quest["objectives"].map(parseQuestObjective)
        : [],
      rewards: isRecord(quest["rewards"]) ? quest["rewards"] : {},
    };
  });
  return {
    name: payload["name"],
    description: payload["description"],
    character_class: payload["character_class"],
    ancestry: payload["ancestry"],
    level: payload["level"],
    xp: payload["xp"],
    xp_to_next_level: payload["xp_to_next_level"],
    xp_progress_percent: payload["xp_progress_percent"],
    attribute_points: payload["attribute_points"],
    gold: payload["gold"],
    hp: payload["hp"],
    max_hp: payload["max_hp"],
    mana: payload["mana"],
    max_mana: payload["max_mana"],
    attributes: payload["attributes"],
    inventory,
    skills,
    quests,
    progression_history: progressionHistory,
  };
}

function parseNarrativeChoice(payload: unknown): NarrativeChoice {
  if (
    !isRecord(payload) ||
    !isString(payload["id"]) ||
    !isString(payload["label"]) ||
    !isNumber(payload["position"]) ||
    !isNullableString(payload["next_node_id"]) ||
    !isRecord(payload["conditions"]) ||
    !isRecord(payload["consequences"])
  ) {
    throw new Error("A API retornou uma escolha narrativa em um formato inesperado.");
  }
  return {
    id: payload["id"],
    label: payload["label"],
    position: payload["position"],
    next_node_id: payload["next_node_id"],
    conditions: payload["conditions"],
    consequences: payload["consequences"],
  };
}

function parseNarrativeVote(payload: unknown): NarrativeVote {
  if (
    !isRecord(payload) ||
    !isString(payload["status"]) ||
    !isNumber(payload["round_number"]) ||
    !isNullableString(payload["deadline_at"]) ||
    typeof payload["allow_vote_change"] !== "boolean" ||
    !isNumber(payload["eligible_count"]) ||
    !isNumber(payload["voted_count"]) ||
    !isNullableString(payload["my_choice_id"]) ||
    !Array.isArray(payload["tally"]) ||
    !(payload["result"] === null || isRecord(payload["result"]))
  ) {
    throw new Error("A API retornou o estado da votação em um formato inesperado.");
  }
  const tally = payload["tally"].map((item): NarrativeVoteTally => {
    if (
      !isRecord(item) ||
      !isString(item["choice_id"]) ||
      !isString(item["label"]) ||
      !isNumber(item["votes"])
    ) {
      throw new Error("A API retornou a apuração em um formato inesperado.");
    }
    return {
      choice_id: item["choice_id"],
      label: item["label"],
      votes: item["votes"],
    };
  });
  return {
    status: payload["status"],
    round_number: payload["round_number"],
    deadline_at: payload["deadline_at"],
    allow_vote_change: payload["allow_vote_change"],
    eligible_count: payload["eligible_count"],
    voted_count: payload["voted_count"],
    my_choice_id: payload["my_choice_id"],
    tally,
    result: payload["result"],
  };
}

function parseNarrativeEvent(payload: unknown): NarrativeEvent {
  if (
    !isRecord(payload) ||
    !isNumber(payload["sequence_number"]) ||
    !isNullableString(payload["actor_user_id"]) ||
    !isString(payload["event_type"]) ||
    !isRecord(payload["payload"]) ||
    !isString(payload["created_at"])
  ) {
    throw new Error("A API retornou um acontecimento em um formato inesperado.");
  }
  return {
    sequence_number: payload["sequence_number"],
    actor_user_id: payload["actor_user_id"],
    event_type: payload["event_type"],
    payload: payload["payload"],
    created_at: payload["created_at"],
  };
}

function parseNarrativeGame(payload: unknown): NarrativeGame {
  if (
    !isRecord(payload) ||
    !isString(payload["session_id"]) ||
    !isString(payload["status"]) ||
    !isRecord(payload["chapter"]) ||
    !isString(payload["chapter"]["id"]) ||
    !isString(payload["chapter"]["title"]) ||
    !isString(payload["chapter"]["summary"]) ||
    !isString(payload["chapter"]["narrative"]) ||
    !isRecord(payload["scene"]) ||
    !isString(payload["scene"]["id"]) ||
    !isString(payload["scene"]["title"]) ||
    !isString(payload["scene"]["narrative"]) ||
    !Array.isArray(payload["scene"]["choices"]) ||
    !Array.isArray(payload["participants"]) ||
    !(payload["vote"] === null || isRecord(payload["vote"])) ||
    !(payload["last_result"] === null || isRecord(payload["last_result"])) ||
    !Array.isArray(payload["history"])
  ) {
    throw new Error("A API retornou a partida narrativa em um formato inesperado.");
  }
  return {
    session_id: payload["session_id"],
    status: payload["status"],
    chapter: {
      id: payload["chapter"]["id"],
      title: payload["chapter"]["title"],
      summary: payload["chapter"]["summary"],
      narrative: payload["chapter"]["narrative"],
    },
    scene: {
      id: payload["scene"]["id"],
      title: payload["scene"]["title"],
      narrative: payload["scene"]["narrative"],
      choices: payload["scene"]["choices"].map(parseNarrativeChoice),
    },
    participants: payload["participants"].map(parseCampaignMember),
    vote: payload["vote"] === null ? null : parseNarrativeVote(payload["vote"]),
    last_result: payload["last_result"],
    history: payload["history"].map(parseNarrativeEvent),
  };
}

async function authenticate(path: string, username: string, password: string): Promise<AuthUser> {
  return parseUser(await requestJson(path, { username, password }));
}

export function registerPlayer(username: string, password: string): Promise<AuthUser> {
  return authenticate("/api/auth/register", username, password);
}

export function loginPlayer(username: string, password: string): Promise<AuthUser> {
  return authenticate("/api/auth/login", username, password);
}

export function loginAdmin(username: string, password: string): Promise<AuthUser> {
  return authenticate("/api/auth/admin/login", username, password);
}

export async function getPlayerSession(): Promise<AuthUser> {
  return parseUser(await requestJson("/api/auth/session"));
}

export async function getAdminSession(): Promise<AuthUser> {
  return parseUser(await requestJson("/api/auth/admin/session"));
}

export async function logoutPlayer(): Promise<void> {
  await requestJson("/api/auth/logout", {});
}

export async function logoutAdmin(): Promise<void> {
  await requestJson("/api/auth/admin/logout", {});
}

export async function getDiscordStatus(): Promise<{ linked: boolean; discord_id: string | null }> {
  const payload = await requestJson("/api/discord/status");
  if (
    !isRecord(payload) ||
    typeof payload["linked"] !== "boolean" ||
    !isNullableString(payload["discord_id"])
  ) {
    throw new Error("A API retornou o vínculo com o Discord em um formato inesperado.");
  }
  return { linked: payload["linked"], discord_id: payload["discord_id"] };
}

export async function startDiscordLink(): Promise<void> {
  const payload = await requestJson("/api/discord/login");
  if (!isRecord(payload) || !isString(payload["authorization_url"])) {
    throw new Error("A API não forneceu o endereço de autorização do Discord.");
  }
  window.location.assign(payload["authorization_url"]);
}

export async function listCampaigns(signal?: AbortSignal): Promise<CampaignSummary[]> {
  const payload = await requestJson("/api/campaigns", undefined, signal);
  if (!Array.isArray(payload)) {
    throw new Error("A API retornou a lista de campanhas em um formato inesperado.");
  }
  return payload.map(parseCampaignSummary);
}

export async function createCampaign(input: {
  title: string;
  description: string;
  max_players: number;
  solo?: boolean;
  difficulty?: "normal" | "hard" | "legendary";
  voting_settings?: {
    allow_vote_change: boolean;
    deadline_seconds: number | null;
    tie_breaker: "unresolved" | "choice_order";
  };
}): Promise<Campaign> {
  return parseCampaign(await requestJson("/api/campaigns", input));
}

export async function joinCampaign(code: string): Promise<Campaign> {
  return parseCampaign(await requestJson("/api/campaigns/join", { code }));
}

export async function pauseCampaign(campaignId: string): Promise<Campaign> {
  return parseCampaign(
    await requestJson(`/api/campaigns/${encodeURIComponent(campaignId)}/pause`, {}),
  );
}

export async function resumeCampaign(campaignId: string): Promise<Campaign> {
  return parseCampaign(
    await requestJson(`/api/campaigns/${encodeURIComponent(campaignId)}/resume`, {}),
  );
}

function parseSoloCharacter(value: unknown): SoloCharacter {
  if (
    !isRecord(value) ||
    !isString(value["id"]) ||
    !isString(value["name"]) ||
    !(value["character_class"] === null || isString(value["character_class"])) ||
    !(value["ancestry"] === null || isString(value["ancestry"])) ||
    !isNumber(value["level"]) ||
    !isNumber(value["hp"]) ||
    !isNumber(value["max_hp"]) ||
    typeof value["active"] !== "boolean"
  ) {
    throw new Error("A API retornou um personagem solo em formato inesperado.");
  }
  return {
    id: value["id"],
    name: value["name"],
    character_class: value["character_class"],
    ancestry: value["ancestry"],
    level: value["level"],
    hp: value["hp"],
    max_hp: value["max_hp"],
    active: value["active"],
  };
}

export async function listSoloCharacters(campaignId: string): Promise<SoloCharacter[]> {
  const payload = await requestJson(`/api/campaigns/${encodeURIComponent(campaignId)}/characters`);
  if (!Array.isArray(payload)) {
    throw new Error("A API retornou a lista de personagens solo em formato inesperado.");
  }
  return payload.map(parseSoloCharacter);
}

export async function createSoloCharacter(
  campaignId: string,
  name: string,
): Promise<SoloCharacter> {
  return parseSoloCharacter(
    await requestJson(`/api/campaigns/${encodeURIComponent(campaignId)}/characters`, { name }),
  );
}

export async function selectSoloCharacter(
  campaignId: string,
  characterId: string,
): Promise<SoloCharacter> {
  return parseSoloCharacter(
    await requestJson(
      `/api/campaigns/${encodeURIComponent(campaignId)}/characters/${encodeURIComponent(characterId)}/active`,
      {},
      undefined,
      "PUT",
    ),
  );
}

export async function getCampaign(campaignId: string, signal?: AbortSignal): Promise<Campaign> {
  return parseCampaign(
    await requestJson(`/api/campaigns/${encodeURIComponent(campaignId)}`, undefined, signal),
  );
}

export async function getCampaignCharacterSheet(campaignId: string): Promise<CharacterSheet> {
  return parseCharacterSheet(
    await requestJson(`/api/campaigns/${encodeURIComponent(campaignId)}/character`),
  );
}

export async function equipCampaignCharacterItem(
  campaignId: string,
  itemId: string,
  slot: string,
): Promise<void> {
  await requestJson(
    `/api/campaigns/${encodeURIComponent(campaignId)}/character/equipment/${encodeURIComponent(itemId)}`,
    { slot },
    undefined,
    "PUT",
  );
}

export async function unequipCampaignCharacterItem(
  campaignId: string,
  itemId: string,
): Promise<void> {
  await requestJson(
    `/api/campaigns/${encodeURIComponent(campaignId)}/character/equipment/${encodeURIComponent(itemId)}`,
    undefined,
    undefined,
    "DELETE",
  );
}

export async function getCampaignQuests(campaignId: string): Promise<CampaignQuest[]> {
  const payload = await requestJson(`/api/campaigns/${encodeURIComponent(campaignId)}/quests`);
  if (!Array.isArray(payload)) {
    throw new Error("A API retornou a lista de missões em um formato inesperado.");
  }
  return payload.map((quest): CampaignQuest => {
    if (
      !isRecord(quest) ||
      !isString(quest["id"]) ||
      !isString(quest["title"]) ||
      !isString(quest["description"]) ||
      !isString(quest["status"]) ||
      !isRecord(quest["progress"]) ||
      !Array.isArray(quest["objectives"]) ||
      !isRecord(quest["rewards"])
    ) {
      throw new Error("A API retornou uma missão em formato inesperado.");
    }
    return {
      id: quest["id"],
      title: quest["title"],
      description: quest["description"],
      status: quest["status"],
      progress: quest["progress"],
      objectives: quest["objectives"].map(parseQuestObjective),
      rewards: quest["rewards"],
    };
  });
}

export async function acceptCampaignQuest(campaignId: string, questId: string): Promise<void> {
  const payload = await requestJson(
    `/api/campaigns/${encodeURIComponent(campaignId)}/quests/${encodeURIComponent(questId)}/accept`,
    {},
  );
  if (!isRecord(payload) || payload["quest_id"] !== questId || !isString(payload["status"])) {
    throw new Error("A API retornou uma confirmação de missão em formato inesperado.");
  }
}

export async function leaveCampaign(campaignId: string): Promise<void> {
  await requestJson(`/api/campaigns/${encodeURIComponent(campaignId)}/leave`, {});
}

export async function updateCampaignReady(
  campaignId: string,
  is_ready: boolean,
): Promise<Campaign> {
  return parseCampaign(
    await requestJson(`/api/campaigns/${encodeURIComponent(campaignId)}/ready`, { is_ready }),
  );
}

export async function updateCampaignCharacter(campaignId: string, name: string): Promise<Campaign> {
  return parseCampaign(
    await requestJson(`/api/campaigns/${encodeURIComponent(campaignId)}/character`, { name }),
  );
}

export async function updateCampaignPresence(
  campaignId: string,
  signal?: AbortSignal,
): Promise<void> {
  await requestJson(`/api/campaigns/${encodeURIComponent(campaignId)}/presence`, {}, signal);
}

export async function startCampaign(campaignId: string): Promise<Campaign> {
  return parseCampaign(
    await requestJson(`/api/campaigns/${encodeURIComponent(campaignId)}/start`, {}),
  );
}

export async function getNarrativeGame(
  campaignId: string,
  signal?: AbortSignal,
): Promise<NarrativeGame> {
  return parseNarrativeGame(
    await requestJson(`/api/campaigns/${encodeURIComponent(campaignId)}/game`, undefined, signal),
  );
}

export async function castNarrativeVote(
  campaignId: string,
  choiceId: string,
): Promise<NarrativeGame> {
  return parseNarrativeGame(
    await requestJson(`/api/campaigns/${encodeURIComponent(campaignId)}/game/vote`, {
      choice_id: choiceId,
    }),
  );
}
