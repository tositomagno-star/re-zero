import { mockDB } from "@/data/mock";
import {
  adminContentRequest,
  isServerId,
  newServerId,
  uploadMonsterImage,
} from "@/lib/admin-content-api";
import type {
  Chapter,
  Character,
  Collection,
  DemoDB,
  Dialogue,
  DropEntry,
  Item,
  Monster,
  Npc,
  Player,
  QuestReward,
  Scene,
  Skill,
  Transaction,
} from "@/types/entities";

type WithId = { id: string } & Record<string, unknown>;

const STORAGE_KEY = "rezero-rpg-demo-v1";
const SERVER_COLLECTIONS = new Set<Collection>([
  "campaigns",
  "chapters",
  "players",
  "characters",
  "npcs",
  "monsters",
  "skills",
  "items",
  "transactions",
  "questRewards",
  "drops",
]);
const ENDPOINTS: Partial<Record<Collection, string>> = {
  campaigns: "campaigns",
  chapters: "chapters",
  players: "players",
  characters: "characters",
  npcs: "npcs",
  monsters: "monsters",
  skills: "skills",
  items: "items",
  transactions: "transactions",
  questRewards: "rewards",
  drops: "drops",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function record(value: unknown, label: string): Record<string, unknown> {
  if (!isRecord(value)) throw new Error(`A API retornou um ${label} inválido.`);
  return value;
}

function records(value: unknown, label: string): Record<string, unknown>[] {
  if (!Array.isArray(value)) throw new Error(`A API retornou uma lista de ${label} inválida.`);
  return value.map((item) => record(item, label));
}

function text(value: unknown, label: string): string {
  if (typeof value !== "string") throw new Error(`A API retornou ${label} em formato inválido.`);
  return value;
}

function optionalText(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function numeric(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value))
    throw new Error(`A API retornou ${label} em formato inválido.`);
  return value;
}

function optionalNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function flag(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

function object(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function uuidFor(id: string | undefined, replacements: Map<string, string>): string {
  if (!id) return newServerId();
  if (isServerId(id)) return id;
  const found = replacements.get(id);
  if (found) return found;
  const idValue = newServerId();
  replacements.set(id, idValue);
  return idValue;
}

function mapDialogue(value: unknown): Dialogue {
  const row = record(value, "diálogo");
  return {
    id: typeof row["id"] === "string" ? row["id"] : newServerId(),
    speaker: text(row["speaker"], "nome do interlocutor"),
    line: text(row["line"], "fala"),
  };
}

function mapScene(value: unknown): Scene {
  const row = record(value, "cena");
  const choices = records(row["choices"] ?? [], "escolha").map((choice) => {
    const conditions = object(choice["conditions"]);
    const consequences = object(choice["consequences"]);
    return {
      id: text(choice["id"], "ID da escolha"),
      label: text(choice["label"], "texto da escolha"),
      nextSceneId: optionalText(choice["next_node_id"]),
      condition: optionalText(conditions["expression"]),
      effect: optionalText(consequences["description"]),
      rewardIds: stringArray(consequences["world_reward_ids"]),
      questIds: stringArray(consequences["complete_quest_ids"]),
      questObjectiveUpdates: Array.isArray(consequences["quest_objective_updates"])
        ? consequences["quest_objective_updates"].flatMap((update) => {
            if (!isRecord(update)) return [];
            const questId = update["quest_id"];
            const objectiveId = update["objective_id"];
            const amount = update["amount"];
            return typeof questId === "string" &&
              typeof objectiveId === "string" &&
              typeof amount === "number"
              ? [{ questId, objectiveId, amount }]
              : [];
          })
        : [],
    };
  });
  return {
    id: text(row["id"], "ID da cena"),
    title: text(row["title"], "título da cena"),
    narrative: optionalText(row["narrative"]),
    dialogues: records(row["dialogues"] ?? [], "diálogo").map(mapDialogue),
    choices,
    npcIds: stringArray(row["npc_ids"]),
    enemyIds: stringArray(row["enemy_ids"]),
    conditions: optionalText(object(row["conditions"])["expression"]),
    isActive: flag(row["is_active"], true),
  };
}

function mapChapter(value: unknown): Chapter {
  const row = record(value, "capítulo");
  return {
    id: text(row["id"], "ID do capítulo"),
    order: numeric(row["position"], "ordem do capítulo") + 1,
    title: text(row["title"], "título do capítulo"),
    summary: optionalText(row["summary"]),
    narrative: optionalText(row["narrative"]),
    status: row["status"] === "published" ? "publicado" : "rascunho",
    scenes: records(row["scenes"] ?? [], "cena").map(mapScene),
    npcIds: stringArray(row["npc_ids"]),
    encounterIds: stringArray(row["enemy_ids"]),
    isActive: flag(row["is_active"], true),
  };
}

function mapNpc(value: unknown): Npc {
  const row = record(value, "NPC");
  const relations = records(row["player_relations"] ?? [], "relação");
  return {
    id: text(row["id"], "ID do NPC"),
    name: text(row["name"], "nome do NPC"),
    description: optionalText(row["description"]),
    personality: optionalText(row["personality"]),
    role: optionalText(row["story_role"]),
    campaignRelation: optionalText(row["campaign_relation"]),
    ...(typeof row["campaign_id"] === "string" ? { campaignId: row["campaign_id"] } : {}),
    playerRelations: relations.flatMap((relation) => {
      const playerId = relation["player_id"];
      const relationship = relation["relationship"];
      return typeof playerId === "string" && typeof relationship === "string"
        ? [{ playerId, relationship }]
        : [];
    }),
    dialogues: records(row["dialogues"] ?? [], "diálogo").map((dialogue) =>
      optionalText(dialogue["line"]),
    ),
    quests: stringArray(row["quests"]),
    relationshipConditions: optionalText(row["relationship_conditions"]),
    placeholder: flag(row["is_placeholder"]),
    status:
      row["status"] === "published"
        ? "publicado"
        : row["status"] === "inactive"
          ? "inactive"
          : "rascunho",
    imageUrl: optionalText(row["image_url"]),
    isActive: flag(row["is_active"], true),
  };
}

function mapMonster(value: unknown): Monster {
  const row = record(value, "monstro");
  const rewards = Array.isArray(row["rewards"])
    ? row["rewards"].flatMap((reward): string[] => {
        if (typeof reward === "string") return [reward];
        if (isRecord(reward) && typeof reward["description"] === "string")
          return [reward["description"]];
        return [];
      })
    : [];
  return {
    id: text(row["id"], "ID do monstro"),
    name: text(row["name"], "nome do monstro"),
    description: optionalText(row["description"]),
    level: numeric(row["level"], "nível do monstro"),
    hp: numeric(row["hp"], "HP do monstro"),
    attack: numeric(row["attack"], "ataque do monstro"),
    defense: numeric(row["defense"], "defesa do monstro"),
    speed: numeric(row["speed"], "velocidade do monstro"),
    abilities: stringArray(row["abilities"]),
    resistances: stringArray(row["resistances"]),
    weaknesses: stringArray(row["weaknesses"]),
    xpReward: numeric(row["xp_reward"], "experiência do monstro"),
    rewards,
    imageUrl: optionalText(row["image_url"]),
    placeholder: false,
    difficulty:
      row["difficulty"] === "easy" || row["difficulty"] === "hard" || row["difficulty"] === "boss"
        ? row["difficulty"]
        : "normal",
    appearanceChance: optionalNumber(row["appearance_chance"], 10000) / 100,
    isActive: flag(row["is_active"], true),
  };
}

function mapSkill(value: unknown): Skill {
  const row = record(value, "habilidade");
  const effects = object(row["effects"]);
  const requirements = object(row["requirements"]);
  const category = text(row["category"], "categoria da habilidade");
  const target = text(row["target"], "alvo da habilidade");
  const powerType = effects["power_type"];
  return {
    id: text(row["id"], "ID da habilidade"),
    name: text(row["name"], "nome da habilidade"),
    category: category as Skill["category"],
    isCareer: category.toLowerCase() === "carreira" || requirements["is_career"] === true,
    description: optionalText(row["description"]),
    manaCost: numeric(row["mana_cost"], "custo de mana"),
    power: optionalNumber(effects["power"]),
    powerType: powerType === "dano" || powerType === "cura" ? powerType : "nenhum",
    effects: optionalText(effects["description"]),
    target: target as Skill["target"],
    levelReq: optionalNumber(requirements["level"], 1),
    cooldown: numeric(row["cooldown_seconds"], "recarga"),
    status: row["status"] === "published" ? "publicado" : "rascunho",
  };
}

function mapItem(value: unknown): Item {
  const row = record(value, "item");
  const attributes = object(row["attributes"]);
  const effects = object(row["effects"]);
  const requirements = object(row["requirements"]);
  return {
    id: text(row["id"], "ID do item"),
    name: text(row["name"], "nome do item"),
    description: optionalText(row["description"]),
    category: text(row["category"], "categoria do item") as Item["category"],
    isCareer:
      String(row["category"]).toLowerCase() === "carreira" || requirements["is_career"] === true,
    rarity: text(row["rarity"], "raridade do item") as Item["rarity"],
    price: numeric(row["price"], "preço do item"),
    weight: numeric(row["weight"], "peso do item"),
    bonuses: optionalText(attributes["description"]),
    effects: optionalText(effects["description"]),
    levelReq: optionalNumber(requirements["level"]),
    stock: numeric(row["stock"], "estoque do item"),
    imageUrl: optionalText(row["image_url"]),
    isActive: flag(row["is_active"], true),
    usage: optionalText(row["usage"]),
  };
}

function mapDrop(value: unknown): DropEntry {
  const row = record(value, "regra de drop");
  return {
    id: text(row["id"], "ID da regra de drop"),
    monsterId: text(row["monster_id"], "monstro da regra de drop"),
    itemId: text(row["item_id"], "item da regra de drop"),
    chance: numeric(row["chance"], "chance de drop"),
    minQuantity: numeric(row["min_quantity"], "quantidade mínima"),
    maxQuantity: numeric(row["max_quantity"], "quantidade máxima"),
  };
}

function mapTransaction(value: unknown): Transaction {
  const row = record(value, "transação");
  return {
    id: text(row["id"], "ID da transação"),
    characterId: text(row["character_id"], "personagem da transação"),
    date: text(row["date"], "data da transação"),
    kind: text(row["kind"], "tipo de transação") as Transaction["kind"],
    description: text(row["description"], "descrição da transação"),
    amount: numeric(row["amount"], "valor da transação"),
  };
}

function mapReward(value: unknown): QuestReward {
  const row = record(value, "recompensa");
  return {
    id: text(row["id"], "ID da recompensa"),
    quest: text(row["quest"], "missão da recompensa"),
    description: optionalText(row["description"]),
    gold: numeric(row["gold"], "ouro da recompensa"),
    xp: numeric(row["xp"], "experiência da recompensa"),
    itemIds: stringArray(row["item_ids"]),
    isActive: flag(row["is_active"], true),
  };
}

function mapCharacter(value: unknown): Character {
  const row = record(value, "personagem");
  const attributes = object(row["attributes"]);
  const inventory = records(row["inventory"] ?? [], "inventário").map((entry) => ({
    itemId: text(entry["item_id"], "item do inventário"),
    qty: numeric(entry["qty"], "quantidade do inventário"),
  }));
  return {
    id: text(row["id"], "ID do personagem"),
    name: text(row["name"], "nome do personagem"),
    playerId: text(row["player_id"], "proprietário do personagem"),
    level: numeric(row["level"], "nível do personagem"),
    xp: numeric(row["xp"], "experiência do personagem"),
    hp: numeric(row["hp"], "HP do personagem"),
    hpMax: numeric(row["hp_max"], "HP máximo do personagem"),
    mana: numeric(row["mana"], "mana do personagem"),
    manaMax: numeric(row["mana_max"], "mana máxima do personagem"),
    attributes: {
      forca: optionalNumber(attributes["forca"]),
      agilidade: optionalNumber(attributes["agilidade"]),
      intelecto: optionalNumber(attributes["intelecto"]),
      vitalidade: optionalNumber(attributes["vitalidade"]),
      espirito: optionalNumber(attributes["espirito"]),
    },
    combatClass: optionalText(row["combat_class"]),
    gold: numeric(row["gold"], "ouro do personagem"),
    equipmentIds: stringArray(row["equipment_ids"]),
    inventory,
    skillIds: stringArray(row["skill_ids"]),
    history: optionalText(row["history"]),
  };
}

function mapPlayer(value: unknown): Player {
  const row = record(value, "jogador");
  return {
    id: text(row["id"], "ID do jogador"),
    discordId: optionalText(row["discord_id"]),
    displayName: text(row["display_name"], "nome do jogador"),
    registeredAt: text(row["registered_at"], "data de cadastro"),
    campaignId: optionalText(row["campaign_id"]),
    status:
      row["status"] === "banido" ? "banido" : row["status"] === "inativo" ? "inativo" : "ativo",
  };
}

function mapCampaign(value: unknown): DemoDB["campaigns"][number] {
  const row = record(value, "campanha");
  const rawStatus = text(row["status"], "estado da campanha");
  const statuses: Record<string, DemoDB["campaigns"][number]["status"]> = {
    waiting: "planejada",
    active: "em_andamento",
    paused: "pausada",
    finished: "concluida",
    completed: "concluida",
  };
  const state = row["world_state"];
  return {
    id: text(row["id"], "ID da campanha"),
    title: text(row["title"], "título da campanha"),
    description: optionalText(row["description"]),
    status: statuses[rawStatus] ?? "planejada",
    minPlayers: numeric(row["min_players"], "mínimo de jogadores"),
    maxPlayers: numeric(row["max_players"], "máximo de jogadores"),
    startChapterId: optionalText(row["start_chapter_id"]) || "none",
    playerIds: stringArray(row["player_ids"]),
    worldState: typeof state === "string" ? state : "",
  };
}

function mappedCollection<K extends Collection>(collection: K, response: unknown): DemoDB[K] {
  const rows = records(response, collection);
  switch (collection) {
    case "campaigns":
      return rows.map(mapCampaign) as DemoDB[K];
    case "chapters":
      return rows.map(mapChapter) as DemoDB[K];
    case "players":
      return rows.map(mapPlayer) as DemoDB[K];
    case "characters":
      return rows.map(mapCharacter) as DemoDB[K];
    case "npcs":
      return rows.map(mapNpc) as DemoDB[K];
    case "monsters":
      return rows.map(mapMonster) as DemoDB[K];
    case "skills":
      return rows.map(mapSkill) as DemoDB[K];
    case "items":
      return rows.map(mapItem) as DemoDB[K];
    case "drops":
      return rows.map(mapDrop) as DemoDB[K];
    case "transactions":
      return rows.map(mapTransaction) as DemoDB[K];
    case "questRewards":
      return rows.map(mapReward) as DemoDB[K];
    default:
      throw new Error(`A coleção ${collection} não está conectada ao servidor.`);
  }
}

function relationRows(value: unknown): { player_id: string; relationship: string }[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => {
    if (!isRecord(entry)) return [];
    const playerId = entry["playerId"];
    const relationship = entry["relationship"];
    return typeof playerId === "string" && typeof relationship === "string"
      ? [{ player_id: playerId, relationship }]
      : [];
  });
}

async function apiPayload<K extends Collection>(
  collection: K,
  entity: DemoDB[K][number],
  sceneIdMap = new Map<string, string>(),
): Promise<Record<string, unknown>> {
  const row = entity as unknown as WithId;
  switch (collection) {
    case "chapters": {
      const chapter = entity as Chapter;
      const scenes = chapter.scenes.map((scene) => ({
        scene,
        id: uuidFor(scene.id, sceneIdMap),
      }));
      const ids = new Map(scenes.map(({ scene, id }) => [scene.id, id]));
      return {
        title: chapter.title,
        summary: chapter.summary,
        narrative: chapter.narrative,
        position: Math.max(0, Math.trunc(chapter.order) - 1),
        status: chapter.status === "publicado" ? "published" : "draft",
        is_active: chapter.isActive ?? true,
        npc_ids: chapter.npcIds,
        enemy_ids: chapter.encounterIds,
        scenes: scenes.map(({ scene, id }, position) => ({
          id,
          title: scene.title,
          narrative: scene.narrative,
          position,
          is_active: scene.isActive ?? true,
          dialogues: scene.dialogues.map((dialogue) => ({
            id: isServerId(dialogue.id) ? dialogue.id : newServerId(),
            speaker: dialogue.speaker,
            line: dialogue.line,
            conditions: {},
          })),
          choices: scene.choices.map((choice, choicePosition) => {
            const target = choice.nextSceneId
              ? (ids.get(choice.nextSceneId) ??
                (isServerId(choice.nextSceneId) ? choice.nextSceneId : undefined))
              : undefined;
            if (choice.nextSceneId && !target) {
              throw new Error(
                `O destino "${choice.nextSceneId}" não corresponde a uma cena salva.`,
              );
            }
            return {
              id: isServerId(choice.id) ? choice.id : newServerId(),
              label: choice.label,
              next_node_id: target ?? null,
              position: choicePosition,
              conditions: choice.condition ? { expression: choice.condition } : {},
              consequences: {
                ...(choice.effect ? { description: choice.effect } : {}),
                ...(choice.rewardIds?.length ? { world_reward_ids: choice.rewardIds } : {}),
                ...(choice.questIds?.length ? { complete_quest_ids: choice.questIds } : {}),
                ...(choice.questObjectiveUpdates?.length
                  ? {
                      quest_objective_updates: choice.questObjectiveUpdates.map((update) => ({
                        quest_id: update.questId,
                        objective_id: update.objectiveId,
                        amount: update.amount,
                      })),
                    }
                  : {}),
              },
            };
          }),
          npc_ids: scene.npcIds ?? [],
          enemy_ids: scene.enemyIds ?? [],
          conditions: scene.conditions ? { expression: scene.conditions } : {},
        })),
      };
    }
    case "npcs": {
      const npc = entity as Npc;
      return {
        campaign_id: npc.campaignId && isServerId(npc.campaignId) ? npc.campaignId : null,
        name: npc.name,
        description: npc.description,
        personality: npc.personality,
        story_role: npc.role,
        status:
          npc.status === "publicado"
            ? "published"
            : npc.status === "inactive"
              ? "inactive"
              : "draft",
        image_url: npc.imageUrl || null,
        campaign_relation: npc.campaignRelation,
        player_relations: relationRows(npc.playerRelations),
        quests: npc.quests,
        relationship_conditions: npc.relationshipConditions,
        is_placeholder: npc.placeholder,
        is_active: npc.isActive ?? true,
        dialogues: npc.dialogues.map((line) => ({
          speaker: npc.name || "NPC",
          line,
          conditions: {},
        })),
      };
    }
    case "items": {
      const item = entity as Item;
      return {
        name: item.name,
        description: item.description,
        category: item.category,
        is_career: item.isCareer === true || item.category === "carreira",
        rarity: item.rarity,
        price: item.price,
        weight: item.weight,
        effects: item.effects ? { description: item.effects } : {},
        requirements: {
          level: item.levelReq,
          is_career: item.isCareer === true || item.category === "carreira",
        },
        attributes: item.bonuses ? { description: item.bonuses } : {},
        stock: item.stock,
        usage: item.usage ?? "",
        is_stackable: item.category === "consumivel" || item.category === "material",
        is_active: item.isActive ?? true,
        image_url: item.imageUrl || null,
      };
    }
    case "monsters": {
      const monster = entity as Monster;
      const imageFile = row["imageFile"];
      return (async () => {
        const imageUrl =
          typeof File !== "undefined" && imageFile instanceof File
            ? await uploadMonsterImage(imageFile)
            : monster.imageUrl || null;
        return {
          name: monster.name,
          description: monster.description,
          level: monster.level,
          hp: monster.hp,
          attack: monster.attack,
          defense: monster.defense,
          speed: monster.speed,
          xp_reward: monster.xpReward,
          difficulty: monster.difficulty ?? "normal",
          abilities: monster.abilities,
          resistances: monster.resistances,
          weaknesses: monster.weaknesses,
          appearance_chance: Math.round((monster.appearanceChance ?? 100) * 100),
          rewards: monster.rewards.map((description) => ({ description })),
          image_url: imageUrl,
          is_active: monster.isActive ?? true,
        };
      })();
    }
    case "skills": {
      const skill = entity as Skill;
      return {
        name: skill.name,
        category: skill.category,
        is_career: skill.isCareer === true || skill.category === "carreira",
        description: skill.description,
        mana_cost: skill.manaCost,
        effects: {
          power: skill.power,
          power_type: skill.powerType,
          description: skill.effects,
        },
        target: skill.target,
        requirements: {
          level: skill.levelReq,
          is_career: skill.isCareer === true || skill.category === "carreira",
        },
        cooldown_seconds: skill.cooldown,
        is_active: skill.status === "publicado",
        status: skill.status === "publicado" ? "published" : "draft",
      };
    }
    case "drops": {
      const drop = entity as DropEntry;
      return {
        enemy_id: drop.monsterId,
        item_id: drop.itemId,
        chance_basis_points: Math.round(drop.chance * 100),
        min_quantity: drop.minQuantity ?? 1,
        max_quantity: drop.maxQuantity ?? 1,
      };
    }
    case "transactions": {
      const transaction = entity as Transaction;
      return {
        character_id: transaction.characterId,
        kind: transaction.kind,
        description: transaction.description,
        amount: Math.abs(transaction.amount),
      };
    }
    case "questRewards": {
      const reward = entity as QuestReward;
      return {
        title: reward.quest,
        description: reward.description ?? "",
        gold: reward.gold,
        xp: reward.xp,
        item_ids: reward.itemIds,
        is_active: reward.isActive ?? true,
      };
    }
    default:
      throw new Error(`A coleção ${collection} não está conectada ao servidor.`);
  }
}

function mapOne<K extends Collection>(collection: K, value: unknown): DemoDB[K][number] {
  const result = mappedCollection(collection, [value]);
  return result[0] as DemoDB[K][number];
}

function cloneDemoDb(): DemoDB {
  return JSON.parse(JSON.stringify(mockDB)) as DemoDB;
}

class LocalDemoService {
  private db: DemoDB | null = null;

  private load(): DemoDB {
    if (this.db) return this.db;
    let db = cloneDemoDb();
    if (typeof window !== "undefined") {
      try {
        const raw = window.localStorage.getItem(STORAGE_KEY);
        if (raw) db = { ...db, ...(JSON.parse(raw) as Partial<DemoDB>) };
      } catch {
        db = cloneDemoDb();
      }
    }
    this.db = db;
    return db;
  }

  private persist(): void {
    if (typeof window !== "undefined" && this.db) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(this.db));
    }
  }

  async list<K extends Collection>(collection: K): Promise<DemoDB[K]> {
    return clone(this.load()[collection]);
  }

  async save<K extends Collection>(
    collection: K,
    entity: DemoDB[K][number],
  ): Promise<DemoDB[K][number]> {
    const rows = this.load()[collection] as unknown as WithId[];
    const row = entity as unknown as WithId;
    const index = rows.findIndex((item) => item.id === row.id);
    if (index >= 0) rows[index] = clone(row);
    else rows.push(clone(row));
    this.persist();
    return clone(entity);
  }

  async remove<K extends Collection>(collection: K, id: string): Promise<void> {
    const db = this.load();
    const rows = db[collection];
    Reflect.set(
      db,
      collection,
      rows.filter((item) => item.id !== id),
    );
    this.persist();
  }

  async reset(): Promise<void> {
    this.db = cloneDemoDb();
    this.persist();
  }
}

const demoService = new LocalDemoService();

export interface DataService {
  isPersistent(collection: Collection): boolean;
  list<K extends Collection>(collection: K): Promise<DemoDB[K]>;
  save<K extends Collection>(collection: K, entity: DemoDB[K][number]): Promise<DemoDB[K][number]>;
  remove<K extends Collection>(collection: K, id: string): Promise<void>;
  reset(): Promise<void>;
}

class HybridDataService implements DataService {
  isPersistent(collection: Collection): boolean {
    return SERVER_COLLECTIONS.has(collection);
  }

  async list<K extends Collection>(collection: K): Promise<DemoDB[K]> {
    if (!this.isPersistent(collection)) return demoService.list(collection);
    const endpoint = ENDPOINTS[collection];
    if (!endpoint) throw new Error(`A coleção ${collection} não tem um endpoint configurado.`);
    const payload = await adminContentRequest(`/api/admin/content/${endpoint}`);
    return mappedCollection(collection, payload);
  }

  async save<K extends Collection>(
    collection: K,
    entity: DemoDB[K][number],
  ): Promise<DemoDB[K][number]> {
    if (!this.isPersistent(collection)) return demoService.save(collection, entity);
    if (collection === "campaigns" || collection === "characters" || collection === "players") {
      throw new Error("Campanhas, contas e personagens são somente leitura neste painel.");
    }
    const endpoint = ENDPOINTS[collection];
    if (!endpoint) throw new Error(`A coleção ${collection} não tem um endpoint configurado.`);
    const row = entity as unknown as WithId;
    const hasServerId = isServerId(row.id);
    if (collection === "transactions" && hasServerId) {
      throw new Error(
        "O histórico financeiro é imutável; transações existentes não podem ser editadas.",
      );
    }
    const replacements = new Map<string, string>();
    const payload = await apiPayload(collection, entity, replacements);
    const path = hasServerId ? `${endpoint}/${row.id}` : endpoint;
    const method = collection === "transactions" || !hasServerId ? "POST" : "PUT";
    const result = await adminContentRequest(`/api/admin/content/${path}`, method, payload);
    return mapOne(collection, result);
  }

  async remove<K extends Collection>(collection: K, id: string): Promise<void> {
    if (!this.isPersistent(collection)) return demoService.remove(collection, id);
    if (collection === "campaigns" || collection === "characters" || collection === "players") {
      throw new Error("Campanhas, contas e personagens não podem ser excluídos pelo painel.");
    }
    if (collection === "transactions") {
      throw new Error("O histórico financeiro é imutável; transações não podem ser excluídas.");
    }
    const endpoint = ENDPOINTS[collection];
    if (!endpoint) throw new Error(`A coleção ${collection} não tem um endpoint configurado.`);
    if (!isServerId(id)) throw new Error("O registro ainda não foi salvo no servidor.");
    await adminContentRequest(`/api/admin/content/${endpoint}/${id}`, "DELETE");
  }

  async reset(): Promise<void> {
    await demoService.reset();
  }
}

export const dataService: DataService = new HybridDataService();

const PREFIX: Record<Collection, string> = {
  campaigns: "camp",
  chapters: "chap",
  players: "ply",
  characters: "chr",
  npcs: "npc",
  monsters: "mon",
  skills: "skl",
  items: "itm",
  transactions: "trx",
  questRewards: "qrw",
  drops: "drp",
  events: "evt",
};

/** Stable, prefixed identifier generator for local demonstration records. */
export function newId(collection: Collection | string): string {
  const prefix = (PREFIX as Record<string, string>)[collection] ?? collection;
  const random =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID().slice(0, 8)
      : Math.random().toString(36).slice(2, 10);
  return `${prefix}_${random}`;
}
