import { AuthApiError } from "@/lib/auth-api";
import { apiOrigin } from "@/lib/api-origin";

const MAX_ASSET_BYTES = 5 * 1024 * 1024;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export type AssetCategory =
  | "characters"
  | "npcs"
  | "allies"
  | "hostiles"
  | "monsters"
  | "minibosses"
  | "bosses"
  | "weapons"
  | "equipment"
  | "spells"
  | "powers"
  | "visual_effects";

export type AssetEntityType = "character" | "npc" | "enemy" | "item" | "skill";

export type AssetAssociation = {
  entity_type: AssetEntityType;
  entity_id: string;
  entity_name: string;
};

export type AssetAssociationWrite = {
  entity_type: AssetEntityType;
  entity_id: string;
};

export type AssetMetadata = {
  name: string;
  description: string;
  category: AssetCategory;
  subcategory: string | null;
  asset_type: string | null;
  is_public: boolean;
  associations: AssetAssociationWrite[];
};

export type AssetGifAnalysis = {
  frame_count: number;
  total_duration_ms: number | null;
  frame_durations_ms: (number | null)[];
  loop: number | null;
};

export type AssetAnalysisMetadata = {
  aspect_ratio: number | null;
  has_transparency: boolean | null;
  gif: AssetGifAnalysis | null;
};

export type AssetRecord = Omit<AssetMetadata, "associations"> & {
  id: string;
  original_filename: string;
  content_type: string;
  extension: string;
  width: number;
  height: number;
  size_bytes: number;
  is_in_use: boolean;
  analysis_metadata: AssetAnalysisMetadata;
  created_at: string;
  updated_at: string;
  url: string;
  associations: AssetAssociation[];
};

export type AssetAssociationOption = AssetAssociationWrite & {
  entity_name: string;
};

export type AnimationTrajectory =
  | "right_to_center"
  | "left_to_center"
  | "right_to_left"
  | "left_to_right"
  | "bottom_to_top"
  | "top_to_bottom"
  | "origin_to_target"
  | "direct_impact"
  | "area_effect";

export type NormalizedPoint = { x: number; y: number };
export type AnimationConfigurationWrite = {
  name: string;
  description: string;
  asset_id: string;
  impact_asset_id: string | null;
  animation_type: "projectile" | "impact" | "area";
  trajectory: AnimationTrajectory;
  movement: "linear" | "ease_in" | "ease_out" | "arc";
  origin: NormalizedPoint;
  target: NormalizedPoint;
  scale: number;
  rotation: number;
  gif_playback_rate: number;
  travel_duration_ms: number;
  travel_speed: number;
  impact_time_ms: number;
  render_layer: number;
  direction: "auto" | "left" | "right" | "up" | "down";
  extra: Record<string, unknown>;
  associations: AssetAssociationWrite[];
};

export type AnimationConfigurationRecord = AnimationConfigurationWrite & {
  id: string;
  associations: (AssetAssociationWrite & { entity_name: string })[];
  is_in_use: boolean;
  created_at: string;
  updated_at: string;
};

const assetCategoryValues = new Set<string>([
  "characters",
  "npcs",
  "allies",
  "hostiles",
  "monsters",
  "minibosses",
  "bosses",
  "weapons",
  "equipment",
  "spells",
  "powers",
  "visual_effects",
]);
const assetEntityTypeValues = new Set<string>(["character", "npc", "enemy", "item", "skill"]);
const animationTrajectoryValues = new Set<string>([
  "right_to_center",
  "left_to_center",
  "right_to_left",
  "left_to_right",
  "bottom_to_top",
  "top_to_bottom",
  "origin_to_target",
  "direct_impact",
  "area_effect",
]);
const animationTypeValues = new Set<string>(["projectile", "impact", "area"]);
const animationMovementValues = new Set<string>(["linear", "ease_in", "ease_out", "arc"]);
const animationDirectionValues = new Set<string>(["auto", "left", "right", "up", "down"]);

function isAssetCategory(value: unknown): value is AssetCategory {
  return typeof value === "string" && assetCategoryValues.has(value);
}

function isAssetEntityType(value: unknown): value is AssetEntityType {
  return typeof value === "string" && assetEntityTypeValues.has(value);
}

function isAnimationTrajectory(value: unknown): value is AnimationTrajectory {
  return typeof value === "string" && animationTrajectoryValues.has(value);
}

function isAnimationType(value: unknown): value is AnimationConfigurationRecord["animation_type"] {
  return typeof value === "string" && animationTypeValues.has(value);
}

function isAnimationMovement(value: unknown): value is AnimationConfigurationRecord["movement"] {
  return typeof value === "string" && animationMovementValues.has(value);
}

function isAnimationDirection(value: unknown): value is AnimationConfigurationRecord["direction"] {
  return typeof value === "string" && animationDirectionValues.has(value);
}

function isAnimationAssociation(
  value: unknown,
): value is AssetAssociationWrite & { entity_name: string } {
  return (
    isRecord(value) &&
    isAssetEntityType(value["entity_type"]) &&
    typeof value["entity_id"] === "string" &&
    typeof value["entity_name"] === "string"
  );
}

function errorMessage(payload: unknown): string {
  if (!isRecord(payload)) return "A operação não foi concluída.";
  const detail = payload["detail"];
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const error = detail[0];
    if (isRecord(error) && typeof error["msg"] === "string") return error["msg"];
  }
  return "A operação não foi concluída.";
}

function parseAsset(value: unknown): AssetRecord {
  const analysisValue =
    isRecord(value) && isRecord(value["analysis_metadata"]) ? value["analysis_metadata"] : {};
  const gifValue = isRecord(analysisValue["gif"]) ? analysisValue["gif"] : null;
  if (
    !isRecord(value) ||
    typeof value["id"] !== "string" ||
    typeof value["name"] !== "string" ||
    typeof value["description"] !== "string" ||
    !isAssetCategory(value["category"]) ||
    typeof value["original_filename"] !== "string" ||
    typeof value["content_type"] !== "string" ||
    typeof value["extension"] !== "string" ||
    typeof value["width"] !== "number" ||
    typeof value["height"] !== "number" ||
    typeof value["size_bytes"] !== "number" ||
    typeof value["is_public"] !== "boolean" ||
    typeof value["is_in_use"] !== "boolean" ||
    typeof value["created_at"] !== "string" ||
    typeof value["updated_at"] !== "string" ||
    typeof value["url"] !== "string" ||
    !Array.isArray(value["associations"])
  ) {
    throw new Error("A API retornou um asset inválido.");
  }
  const aspectRatio = analysisValue["aspect_ratio"];
  const transparency = analysisValue["has_transparency"];
  const gifAnalysis =
    gifValue &&
    typeof gifValue["frame_count"] === "number" &&
    Array.isArray(gifValue["frame_durations_ms"]) &&
    gifValue["frame_durations_ms"].every(
      (duration) => duration === null || typeof duration === "number",
    ) &&
    (gifValue["total_duration_ms"] === null || typeof gifValue["total_duration_ms"] === "number") &&
    (gifValue["loop"] === null || typeof gifValue["loop"] === "number")
      ? {
          frame_count: gifValue["frame_count"],
          frame_durations_ms: gifValue["frame_durations_ms"] as (number | null)[],
          total_duration_ms: gifValue["total_duration_ms"] as number | null,
          loop: gifValue["loop"] as number | null,
        }
      : null;
  const associations = value["associations"].map((item): AssetAssociation => {
    if (
      !isRecord(item) ||
      !isAssetEntityType(item["entity_type"]) ||
      typeof item["entity_id"] !== "string" ||
      typeof item["entity_name"] !== "string"
    ) {
      throw new Error("A API retornou um vínculo de asset inválido.");
    }
    return {
      entity_type: item["entity_type"],
      entity_id: item["entity_id"],
      entity_name: item["entity_name"],
    };
  });
  return {
    id: value["id"],
    name: value["name"],
    description: value["description"],
    category: value["category"],
    subcategory: typeof value["subcategory"] === "string" ? value["subcategory"] : null,
    asset_type: typeof value["asset_type"] === "string" ? value["asset_type"] : null,
    is_public: value["is_public"],
    is_in_use: value["is_in_use"],
    associations,
    original_filename: value["original_filename"],
    content_type: value["content_type"],
    extension: value["extension"],
    width: value["width"],
    height: value["height"],
    size_bytes: value["size_bytes"],
    analysis_metadata: {
      aspect_ratio: typeof aspectRatio === "number" ? aspectRatio : null,
      has_transparency: typeof transparency === "boolean" ? transparency : null,
      gif: gifAnalysis,
    },
    created_at: value["created_at"],
    updated_at: value["updated_at"],
    url: value["url"],
  };
}

export async function adminContentRequest(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<unknown> {
  const headers = new Headers();
  const init: RequestInit = { method, credentials: "include", headers };
  if (body !== undefined) {
    headers.set("Content-Type", "application/json");
    init.body = JSON.stringify(body);
  }
  return responsePayload(await fetch(`${apiOrigin}${path}`, init));
}

export async function listAssets(
  category: AssetCategory | "",
  search: string,
): Promise<AssetRecord[]> {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (search.trim()) params.set("search", search.trim());
  const query = params.size > 0 ? `?${params.toString()}` : "";
  const payload = await adminContentRequest(`/api/admin/assets${query}`);
  if (!Array.isArray(payload)) throw new Error("A API retornou uma lista de assets inválida.");
  return payload.map(parseAsset);
}

export async function listAssetAssociationOptions(): Promise<AssetAssociationOption[]> {
  const collections: { entity_type: AssetEntityType; path: string }[] = [
    { entity_type: "character", path: "/api/admin/content/characters" },
    { entity_type: "npc", path: "/api/admin/content/npcs" },
    { entity_type: "enemy", path: "/api/admin/content/monsters" },
    { entity_type: "item", path: "/api/admin/content/items" },
    { entity_type: "skill", path: "/api/admin/content/skills" },
  ];
  const results = await Promise.all(
    collections.map(async ({ entity_type, path }) => {
      const payload = await adminContentRequest(path);
      if (!Array.isArray(payload)) throw new Error("A API retornou entidades inválidas.");
      return payload.flatMap((entry): AssetAssociationOption[] => {
        if (
          !isRecord(entry) ||
          typeof entry["id"] !== "string" ||
          typeof entry["name"] !== "string"
        ) {
          return [];
        }
        return [
          {
            entity_type,
            entity_id: entry["id"],
            entity_name: entry["name"],
          },
        ];
      });
    }),
  );
  return results.flat();
}

export async function createAsset(file: File, metadata: AssetMetadata): Promise<AssetRecord> {
  if (file.size > MAX_ASSET_BYTES) throw new Error("A imagem excede o limite de 5 MB.");
  const form = new FormData();
  form.set("name", metadata.name);
  form.set("description", metadata.description);
  form.set("category", metadata.category);
  if (metadata.subcategory) form.set("subcategory", metadata.subcategory);
  if (metadata.asset_type) form.set("asset_type", metadata.asset_type);
  form.set("is_public", String(metadata.is_public));
  form.set("associations", JSON.stringify(metadata.associations));
  form.set("file", file);
  const response = await fetch(`${apiOrigin}/api/admin/assets`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  return parseAsset(await responsePayload(response));
}

export async function updateAssetMetadata(
  assetId: string,
  metadata: AssetMetadata,
): Promise<AssetRecord> {
  const payload = await adminContentRequest(
    `/api/admin/assets/${encodeURIComponent(assetId)}`,
    "PUT",
    metadata,
  );
  return parseAsset(payload);
}

export async function replaceAssetFile(assetId: string, file: File): Promise<AssetRecord> {
  if (file.size > MAX_ASSET_BYTES) throw new Error("A imagem excede o limite de 5 MB.");
  const form = new FormData();
  form.set("file", file);
  const response = await fetch(
    `${apiOrigin}/api/admin/assets/${encodeURIComponent(assetId)}/file`,
    {
      method: "PUT",
      credentials: "include",
      body: form,
    },
  );
  return parseAsset(await responsePayload(response));
}

export async function getAdminAssetFile(assetId: string): Promise<Blob> {
  const response = await fetch(
    `${apiOrigin}/api/admin/assets/${encodeURIComponent(assetId)}/file`,
    { credentials: "include" },
  );
  if (!response.ok) {
    const payload = await responsePayload(response);
    throw new Error(errorMessage(payload));
  }
  return response.blob();
}

function parseAnimation(value: unknown): AnimationConfigurationRecord {
  const point = (entry: unknown): entry is NormalizedPoint =>
    isRecord(entry) &&
    typeof entry["x"] === "number" &&
    entry["x"] >= 0 &&
    entry["x"] <= 1 &&
    typeof entry["y"] === "number" &&
    entry["y"] >= 0 &&
    entry["y"] <= 1;
  const associations = isRecord(value) ? value["associations"] : undefined;
  if (
    !isRecord(value) ||
    typeof value["id"] !== "string" ||
    typeof value["name"] !== "string" ||
    typeof value["description"] !== "string" ||
    typeof value["asset_id"] !== "string" ||
    (value["impact_asset_id"] !== null && typeof value["impact_asset_id"] !== "string") ||
    !isAnimationType(value["animation_type"]) ||
    !isAnimationTrajectory(value["trajectory"]) ||
    !isAnimationMovement(value["movement"]) ||
    !point(value["origin"]) ||
    !point(value["target"]) ||
    typeof value["scale"] !== "number" ||
    typeof value["rotation"] !== "number" ||
    typeof value["gif_playback_rate"] !== "number" ||
    typeof value["travel_duration_ms"] !== "number" ||
    typeof value["travel_speed"] !== "number" ||
    typeof value["impact_time_ms"] !== "number" ||
    typeof value["render_layer"] !== "number" ||
    !isAnimationDirection(value["direction"]) ||
    !Array.isArray(associations) ||
    !associations.every(isAnimationAssociation) ||
    typeof value["is_in_use"] !== "boolean" ||
    typeof value["created_at"] !== "string" ||
    typeof value["updated_at"] !== "string"
  ) {
    throw new Error("A API retornou uma configuração de animação inválida.");
  }
  return {
    id: value["id"],
    name: value["name"],
    description: value["description"],
    asset_id: value["asset_id"],
    impact_asset_id: value["impact_asset_id"],
    animation_type: value["animation_type"],
    trajectory: value["trajectory"],
    movement: value["movement"],
    origin: value["origin"],
    target: value["target"],
    scale: value["scale"],
    rotation: value["rotation"],
    gif_playback_rate: value["gif_playback_rate"],
    travel_duration_ms: value["travel_duration_ms"],
    travel_speed: value["travel_speed"],
    impact_time_ms: value["impact_time_ms"],
    render_layer: value["render_layer"],
    direction: value["direction"],
    extra: isRecord(value["extra"]) ? value["extra"] : {},
    associations,
    is_in_use: value["is_in_use"],
    created_at: value["created_at"],
    updated_at: value["updated_at"],
  };
}

export async function listAnimationConfigurations(): Promise<AnimationConfigurationRecord[]> {
  const payload = await adminContentRequest("/api/admin/animations");
  if (!Array.isArray(payload)) {
    throw new Error("A API retornou uma lista de animações inválida.");
  }
  return payload.map(parseAnimation);
}

export async function saveAnimationConfiguration(
  configuration: AnimationConfigurationWrite,
  id?: string,
): Promise<AnimationConfigurationRecord> {
  const payload = await adminContentRequest(
    id ? `/api/admin/animations/${encodeURIComponent(id)}` : "/api/admin/animations",
    id ? "PUT" : "POST",
    configuration,
  );
  return parseAnimation(payload);
}

export async function deleteAnimationConfiguration(id: string): Promise<void> {
  await adminContentRequest(`/api/admin/animations/${encodeURIComponent(id)}`, "DELETE");
}

export async function deleteAsset(assetId: string): Promise<void> {
  await adminContentRequest(
    `/api/admin/assets/${encodeURIComponent(assetId)}?confirm=true`,
    "DELETE",
  );
}

export function assetFileUrl(url: string): string {
  return url.startsWith("/") ? `${apiOrigin}${url}` : url;
}

export async function uploadMonsterImage(file: File): Promise<string> {
  if (!file.name.toLowerCase().endsWith(".png")) {
    throw new Error("Selecione um arquivo PNG.");
  }
  if (file.size > 5 * 1024 * 1024) {
    throw new Error("A imagem excede o limite de 5 MB.");
  }
  const response = await fetch(`${apiOrigin}/api/admin/content/monsters/images`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "image/png" },
    body: file,
  });
  const payload = await responsePayload(response);
  if (!isRecord(payload) || typeof payload["url"] !== "string") {
    throw new Error("A API retornou um endereço de imagem inválido.");
  }
  return payload["url"];
}

async function responsePayload(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new AuthApiError("A API retornou uma resposta inválida.", response.status);
  }
  if (!response.ok) {
    throw new AuthApiError(errorMessage(payload), response.status);
  }
  return payload;
}

export function isServerId(id: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id);
}

export function newServerId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function")
    return crypto.randomUUID();
  const bytes = new Uint8Array(16);
  if (typeof crypto !== "undefined") crypto.getRandomValues(bytes);
  else for (let index = 0; index < bytes.length; index += 1) bytes[index] = Math.random() * 256;
  bytes[6] = (bytes[6]! & 0x0f) | 0x40;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;
  const hex = [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
