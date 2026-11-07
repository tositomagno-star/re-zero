// Entity types shared by the UI and the (future) FastAPI backend.
// IDs are stable string identifiers with a type prefix (e.g. "camp_001").

export type PublishStatus = "rascunho" | "publicado";
export type CampaignStatus = "planejada" | "em_andamento" | "pausada" | "concluida";
export type PlayerStatus = "ativo" | "inativo" | "banido";

export interface Campaign {
  id: string;
  title: string;
  description: string;
  status: CampaignStatus;
  minPlayers: number;
  maxPlayers: number;
  startChapterId: string;
  playerIds: string[];
  worldState: string;
}

export interface Choice {
  id: string;
  label: string;
  nextSceneId: string;
  condition: string;
  effect: string;
  rewardIds?: string[];
  questIds?: string[];
  questObjectiveUpdates?: {
    questId: string;
    objectiveId: string;
    amount: number;
  }[];
}

export interface Dialogue {
  id: string;
  speaker: string;
  line: string;
}

export interface Scene {
  id: string;
  title: string;
  narrative: string;
  dialogues: Dialogue[];
  choices: Choice[];
  npcIds?: string[];
  enemyIds?: string[];
  conditions?: string;
  isActive?: boolean;
}

export interface Chapter {
  id: string;
  order: number;
  title: string;
  summary: string;
  narrative: string;
  status: PublishStatus;
  scenes: Scene[];
  npcIds: string[];
  encounterIds: string[];
  isActive?: boolean;
}

export interface Player {
  id: string;
  discordId: string;
  displayName: string;
  registeredAt: string;
  campaignId: string;
  status: PlayerStatus;
}

export interface Attributes {
  forca: number;
  agilidade: number;
  intelecto: number;
  vitalidade: number;
  espirito: number;
}

export interface Character {
  id: string;
  name: string;
  playerId: string;
  level: number;
  xp: number;
  hp: number;
  hpMax: number;
  mana: number;
  manaMax: number;
  attributes: Attributes;
  combatClass: string;
  gold: number;
  equipmentIds: string[];
  inventory: { itemId: string; qty: number }[];
  skillIds: string[];
  history: string;
}

export interface Npc {
  id: string;
  name: string;
  description: string;
  personality: string;
  role: string;
  campaignRelation: string;
  campaignId?: string;
  playerRelations?: { playerId: string; relationship: string }[];
  dialogues: string[];
  quests: string[];
  relationshipConditions: string;
  placeholder: boolean;
  status?: PublishStatus | "inactive";
  imageUrl?: string;
  isActive?: boolean;
}

export interface Monster {
  id: string;
  name: string;
  description: string;
  level: number;
  hp: number;
  attack: number;
  defense: number;
  speed: number;
  abilities: string[];
  resistances: string[];
  weaknesses: string[];
  xpReward: number;
  rewards: string[];
  imageUrl: string;
  placeholder: boolean;
  difficulty?: "easy" | "normal" | "hard" | "boss";
  appearanceChance?: number;
  isActive?: boolean;
}

export type SkillCategory =
  "fogo" | "agua" | "vento" | "terra" | "yin" | "yang" | "fisica" | "suporte" | "carreira";
export type SkillTarget = "proprio" | "aliado" | "inimigo" | "area";

export interface Skill {
  id: string;
  name: string;
  category: SkillCategory;
  description: string;
  manaCost: number;
  power: number;
  powerType: "dano" | "cura" | "nenhum";
  effects: string;
  target: SkillTarget;
  levelReq: number;
  cooldown: number;
  status: PublishStatus;
  isCareer?: boolean;
}

export type ItemCategory =
  "arma" | "armadura" | "acessorio" | "consumivel" | "material" | "missao" | "carreira";
export type Rarity = "comum" | "incomum" | "raro" | "epico" | "lendario";

export interface Item {
  id: string;
  name: string;
  description: string;
  category: ItemCategory;
  rarity: Rarity;
  price: number;
  weight: number;
  bonuses: string;
  effects: string;
  levelReq: number;
  stock: number;
  imageUrl?: string;
  isActive?: boolean;
  usage?: string;
  isCareer?: boolean;
}

export interface Transaction {
  id: string;
  characterId: string;
  date: string;
  kind: "compra" | "venda" | "recompensa" | "drop";
  description: string;
  amount: number;
}

export interface QuestReward {
  id: string;
  quest: string;
  gold: number;
  xp: number;
  itemIds: string[];
  description?: string;
  isActive?: boolean;
}

export interface DropEntry {
  id: string;
  monsterId: string;
  itemId: string;
  chance: number;
  minQuantity?: number;
  maxQuantity?: number;
}

export interface ActivityEvent {
  id: string;
  date: string;
  text: string;
  kind: "campanha" | "capitulo" | "jogador" | "criatura" | "item";
}

export interface DemoDB {
  campaigns: Campaign[];
  chapters: Chapter[];
  players: Player[];
  characters: Character[];
  npcs: Npc[];
  monsters: Monster[];
  skills: Skill[];
  items: Item[];
  transactions: Transaction[];
  questRewards: QuestReward[];
  drops: DropEntry[];
  events: ActivityEvent[];
}

export type Collection = keyof DemoDB;
