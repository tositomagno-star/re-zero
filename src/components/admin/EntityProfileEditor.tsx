import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/common/ui-bits";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  createAsset,
  adminContentRequest,
  listAnimationConfigurations,
  listAssets,
  type AssetCategory,
} from "@/lib/admin-content-api";

type EntityType = "character" | "npc" | "enemy" | "item" | "skill";
type RecordValue = Record<string, unknown>;
type ProfileAvailability = "draft" | "available" | "archived";
type AssetRole = "main_image" | "sprite" | "idle" | "attack" | "damage" | "defeat" | "impact";
type AnimationRole =
  "idle" | "attack" | "damage" | "defeat" | "impact" | "ability" | "weapon_attack";

type EntityOption = { id: string; name: string };
type EntityProfile = {
  id: string;
  entity_type: EntityType;
  entity_id: string;
  kind: string;
  availability: ProfileAvailability;
  scale: number;
  orientation: "auto" | "left" | "right";
  default_position: { x: number; y: number };
  attributes: Record<string, number>;
  settings: RecordValue;
  assets: { role: AssetRole; asset_id: string }[];
  animations: { role: AnimationRole; animation_id: string }[];
  skills: { skill_id: string; attack_speed_override: number | null }[];
  equipment_ids: string[];
};

const entityEndpoints: Record<EntityType, string> = {
  character: "/api/admin/content/characters",
  npc: "/api/admin/content/npcs",
  enemy: "/api/admin/content/monsters",
  item: "/api/admin/content/items",
  skill: "/api/admin/content/skills",
};

const combatGifCategories: Record<EntityType, AssetCategory> = {
  character: "characters",
  npc: "npcs",
  enemy: "monsters",
  item: "equipment",
  skill: "spells",
};

const supplementaryAssetSlots: { value: AssetRole; label: string }[] = [
  { value: "main_image", label: "Imagem principal" },
  { value: "sprite", label: "Sprite" },
  { value: "idle", label: "GIF idle" },
  { value: "damage", label: "GIF de dano" },
  { value: "defeat", label: "GIF de derrota" },
];

const animationSlots: { value: AnimationRole; label: string }[] = [
  { value: "idle", label: "Idle" },
  { value: "attack", label: "Ataque" },
  { value: "damage", label: "Dano" },
  { value: "defeat", label: "Derrota" },
  { value: "impact", label: "Impacto" },
  { value: "ability", label: "Habilidade" },
  { value: "weapon_attack", label: "Ataque da arma" },
];

const trajectories = [
  "right_to_center",
  "left_to_center",
  "right_to_left",
  "left_to_right",
  "bottom_to_top",
  "top_to_bottom",
  "origin_to_target",
  "direct_impact",
  "area_effect",
];

function isRecord(value: unknown): value is RecordValue {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseEntities(value: unknown): EntityOption[] {
  if (!Array.isArray(value)) throw new Error("A API retornou uma lista de entidades inválida.");
  return value.map((entry) => {
    if (!isRecord(entry) || typeof entry["id"] !== "string" || typeof entry["name"] !== "string") {
      throw new Error("A API retornou uma entidade com formato inválido.");
    }
    return { id: entry["id"], name: entry["name"] };
  });
}

function parseProfiles(value: unknown): EntityProfile[] {
  if (!Array.isArray(value)) throw new Error("A API retornou uma lista de perfis inválida.");
  return value.map((entry) => {
    if (
      !isRecord(entry) ||
      typeof entry["id"] !== "string" ||
      typeof entry["entity_type"] !== "string" ||
      !["character", "npc", "enemy", "item", "skill"].includes(entry["entity_type"]) ||
      typeof entry["entity_id"] !== "string" ||
      typeof entry["kind"] !== "string" ||
      !["draft", "available", "archived"].includes(String(entry["availability"])) ||
      typeof entry["scale"] !== "number" ||
      !["auto", "left", "right"].includes(String(entry["orientation"])) ||
      !isRecord(entry["default_position"]) ||
      typeof entry["default_position"]["x"] !== "number" ||
      typeof entry["default_position"]["y"] !== "number" ||
      !isRecord(entry["attributes"]) ||
      !isRecord(entry["settings"]) ||
      !Array.isArray(entry["assets"]) ||
      !Array.isArray(entry["animations"]) ||
      !Array.isArray(entry["skills"]) ||
      !Array.isArray(entry["equipment_ids"])
    ) {
      throw new Error("A API retornou uma configuração de entidade inválida.");
    }
    const attributes: Record<string, number> = {};
    for (const [key, attribute] of Object.entries(entry["attributes"])) {
      if (typeof attribute !== "number" || !Number.isFinite(attribute)) {
        throw new Error("A API retornou atributos de entidade inválidos.");
      }
      attributes[key] = attribute;
    }
    const assets = entry["assets"].map((binding) => {
      if (
        !isRecord(binding) ||
        typeof binding["role"] !== "string" ||
        typeof binding["asset_id"] !== "string"
      ) {
        throw new Error("A API retornou uma associação de asset inválida.");
      }
      return { role: binding["role"] as AssetRole, asset_id: binding["asset_id"] };
    });
    const animations = entry["animations"].map((binding) => {
      if (
        !isRecord(binding) ||
        typeof binding["role"] !== "string" ||
        typeof binding["animation_id"] !== "string"
      ) {
        throw new Error("A API retornou uma associação de animação inválida.");
      }
      return {
        role: binding["role"] as AnimationRole,
        animation_id: binding["animation_id"],
      };
    });
    const skills = entry["skills"].map((association) => {
      if (
        !isRecord(association) ||
        typeof association["skill_id"] !== "string" ||
        (association["attack_speed_override"] !== null &&
          typeof association["attack_speed_override"] !== "number")
      ) {
        throw new Error("A API retornou uma associação de habilidade inválida.");
      }
      return {
        skill_id: association["skill_id"],
        attack_speed_override: association["attack_speed_override"],
      };
    });
    const equipmentIds = entry["equipment_ids"].map((id) => {
      if (typeof id !== "string") {
        throw new Error("A API retornou associações de equipamento inválidas.");
      }
      return id;
    });
    return {
      id: entry["id"],
      entity_type: entry["entity_type"] as EntityType,
      entity_id: entry["entity_id"],
      kind: entry["kind"],
      availability: entry["availability"] as ProfileAvailability,
      scale: entry["scale"],
      orientation: entry["orientation"] as EntityProfile["orientation"],
      default_position: {
        x: entry["default_position"]["x"],
        y: entry["default_position"]["y"],
      },
      attributes,
      settings: entry["settings"],
      assets,
      animations,
      skills,
      equipment_ids: equipmentIds,
    };
  });
}

function newProfile(entityType: EntityType, entityId: string): Omit<EntityProfile, "id"> {
  const defaults: Record<EntityType, RecordValue> = {
    character: {
      actor_type: "playable_character",
      attack_release_delay_ms: 500,
      attack_animation_duration_ms: 700,
    },
    npc: { actor_type: "npc" },
    enemy: {
      category: "common",
      default_attack_speed: 1,
      gold_reward: 0,
      special_rewards: [],
      boss_difficulty: "common",
      max_attacks_per_turn: 1,
      can_interrupt_turns: false,
      strategy: "baseline",
      attack_release_delay_ms: 500,
      attack_animation_duration_ms: 700,
    },
    item: {
      weapon_type: "",
      attack: 0,
      defense: 0,
      reach: 1,
      speed: 1,
      animation_display: "with_character",
      special_effects: {},
    },
    skill: {
      skill_type: "fisica",
      reach: 1,
      target_type: "single",
      default_speed: 1,
      travel_duration_ms: 700,
      impact_time_ms: 0,
      attack_release_delay_ms: 500,
      attack_animation_duration_ms: 700,
      projectile_only: false,
      combat_visual_mode: "separated",
      trajectory: "origin_to_target",
      direction: "auto",
      additional_effects: {},
    },
  };
  return {
    entity_type: entityType,
    entity_id: entityId,
    kind: "",
    availability: "draft",
    scale: 1,
    orientation: "auto",
    default_position: { x: 0.5, y: 0.5 },
    attributes: {},
    settings: defaults[entityType],
    assets: [],
    animations: [],
    skills: [],
    equipment_ids: [],
  };
}

function jsonText(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value ?? {}, null, 2);
}

function JsonEditor({
  label,
  value,
  onChange,
}: {
  label: string;
  value: unknown;
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-2 text-sm font-medium">
      {label}
      <textarea
        className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
        value={jsonText(value)}
        onChange={(event) => onChange(event.target.value)}
        spellCheck={false}
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-2 text-sm font-medium">
      {label}
      <select
        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function EntityProfileEditor({ entityType }: { entityType: EntityType }) {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState("");
  const [draft, setDraft] = useState<Omit<EntityProfile, "id"> | null>(null);
  const [attributesJson, setAttributesJson] = useState("{}");
  const [settingsJson, setSettingsJson] = useState<Record<string, string>>({});
  const [uploadingRole, setUploadingRole] = useState<AssetRole | null>(null);
  const entities = useQuery({
    queryKey: ["admin-content", "profile-entities", entityType],
    queryFn: async () => parseEntities(await adminContentRequest(entityEndpoints[entityType])),
  });
  const profiles = useQuery({
    queryKey: ["admin-content", "entity-profiles", entityType],
    queryFn: async () =>
      parseProfiles(await adminContentRequest(`/api/admin/content/profiles/${entityType}`)),
  });
  const skills = useQuery({
    queryKey: ["admin-content", "profile-entities", "skill-options"],
    queryFn: async () => parseEntities(await adminContentRequest(entityEndpoints.skill)),
  });
  const items = useQuery({
    queryKey: ["admin-content", "profile-entities", "item-options"],
    queryFn: async () => parseEntities(await adminContentRequest(entityEndpoints.item)),
  });
  const assets = useQuery({
    queryKey: ["admin-content", "profile-assets"],
    queryFn: () => listAssets("", ""),
  });
  const animations = useQuery({
    queryKey: ["admin-content", "profile-animations"],
    queryFn: listAnimationConfigurations,
  });

  const selectedEntity = entities.data?.find((entity) => entity.id === selectedId);
  const activeProfile = useMemo(
    () => profiles.data?.find((profile) => profile.entity_id === selectedId),
    [profiles.data, selectedId],
  );
  const supportingErrors = [
    profiles.error,
    assets.error,
    animations.error,
    entityType === "enemy" || entityType === "npc" ? skills.error : null,
    entityType === "npc" ? items.error : null,
  ].filter((error): error is Error => error instanceof Error);
  const dependenciesReady =
    Boolean(profiles.data && assets.data && animations.data) &&
    ((entityType !== "enemy" && entityType !== "npc") || Boolean(skills.data)) &&
    (entityType !== "npc" || Boolean(items.data));

  useEffect(() => {
    if (!selectedId) {
      setDraft(null);
      return;
    }
    const profile = activeProfile ?? newProfile(entityType, selectedId);
    setDraft({
      entity_type: entityType,
      entity_id: selectedId,
      kind: profile.kind,
      availability: profile.availability,
      scale: profile.scale,
      orientation: profile.orientation,
      default_position: profile.default_position,
      attributes: profile.attributes ?? {},
      settings: profile.settings,
      assets: profile.assets,
      animations: profile.animations,
      skills: profile.skills,
      equipment_ids: profile.equipment_ids,
    });
    setAttributesJson(jsonText(profile["attributes"] ?? {}));
    setSettingsJson({});
  }, [activeProfile, entityType, selectedId]);

  const save = useMutation({
    mutationFn: async () => {
      if (!draft || !selectedId) throw new Error("Selecione uma entidade para salvar.");
      let attributes: unknown;
      try {
        attributes = JSON.parse(attributesJson);
      } catch {
        throw new Error("Atributos precisa ser um JSON válido.");
      }
      if (!isRecord(attributes)) throw new Error("Atributos precisa ser um objeto JSON.");
      const settings = { ...draft.settings };
      for (const [key, text] of Object.entries(settingsJson)) {
        if (
          key === "special_rewards" ||
          key === "special_effects" ||
          key === "additional_effects"
        ) {
          try {
            settings[key] = JSON.parse(text);
          } catch {
            throw new Error(`${key} precisa ser um JSON válido.`);
          }
        } else if (typeof settings[key] === "number") {
          const number = Number(text);
          if (!Number.isFinite(number)) throw new Error(`${key} precisa ser um número válido.`);
          settings[key] = number;
        } else if (typeof settings[key] === "boolean") {
          settings[key] = text === "true";
        } else {
          settings[key] = text;
        }
      }
      return adminContentRequest(
        `/api/admin/content/profiles/${entityType}/${encodeURIComponent(selectedId)}`,
        "PUT",
        { ...draft, attributes, settings },
      );
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["admin-content", "entity-profiles", entityType],
      });
      toast.success("Configurações da entidade salvas.");
    },
    onError: (error) =>
      toast.error("Não foi possível salvar as configurações.", {
        description: error instanceof Error ? error.message : String(error),
      }),
  });
  const remove = useMutation({
    mutationFn: async () => {
      if (!selectedId) throw new Error("Selecione uma entidade para remover a configuração.");
      return adminContentRequest(
        `/api/admin/content/profiles/${entityType}/${encodeURIComponent(selectedId)}?confirm=true`,
        "DELETE",
      );
    },
    onSuccess: async () => {
      setSelectedId("");
      setDraft(null);
      await queryClient.invalidateQueries({
        queryKey: ["admin-content", "entity-profiles", entityType],
      });
      toast.success("Configuração removida; a entidade original foi preservada.");
    },
    onError: (error) =>
      toast.error("Não foi possível remover a configuração.", {
        description: error instanceof Error ? error.message : String(error),
      }),
  });

  function duplicateProfile(sourceId: string) {
    const source = profiles.data?.find((profile) => profile.id === sourceId);
    if (!source || !selectedId) return;
    setDraft({
      entity_type: entityType,
      entity_id: selectedId,
      kind: source.kind,
      availability: "draft",
      scale: source.scale,
      orientation: source.orientation,
      default_position: source.default_position,
      attributes: source.attributes,
      settings: source.settings,
      assets: source.assets,
      animations: source.animations,
      skills: source.skills,
      equipment_ids: source.equipment_ids,
    });
    setAttributesJson(jsonText(source.attributes));
    setSettingsJson({});
  }

  function updateDraft(patch: Partial<Omit<EntityProfile, "id">>) {
    setDraft((current) => (current ? { ...current, ...patch } : current));
  }

  function updateSettings(key: string, value: string) {
    setSettingsJson((current) => ({ ...current, [key]: value }));
  }

  async function uploadCombatGif(role: AssetRole, file: File) {
    if (!selectedId || !selectedEntity) return;
    if (file.type !== "image/gif" && !file.name.toLowerCase().endsWith(".gif")) {
      toast.error("Selecione um arquivo GIF.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error("O GIF excede o limite de 5 MB.");
      return;
    }
    setUploadingRole(role);
    try {
      const asset = await createAsset(file, {
        name: file.name.replace(/\.gif$/i, "").trim() || "GIF de combate",
        description: `GIF de ${role === "attack" ? "execução" : "projétil"} de ${selectedEntity.name}.`,
        category: combatGifCategories[entityType],
        subcategory: role === "attack" ? "execution" : "projectile",
        asset_type: role === "attack" ? "execution_gif" : "projectile_gif",
        is_public: false,
        associations: [{ entity_type: entityType, entity_id: selectedId }],
      });
      setDraft((current) =>
        current
          ? {
              ...current,
              assets: [
                ...current.assets.filter((entry) => entry.role !== role),
                { role, asset_id: asset.id },
              ],
            }
          : current,
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-content", "profile-assets"] }),
        queryClient.invalidateQueries({ queryKey: ["admin-assets"] }),
      ]);
      toast.success(`GIF de ${role === "attack" ? "execução" : "projétil"} enviado e selecionado.`);
    } catch (error) {
      toast.error("Não foi possível enviar o GIF.", {
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setUploadingRole(null);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    save.mutate();
  }

  const settings = draft?.settings ?? {};
  const field = (key: string, label: string, type: "text" | "number" = "text") => (
    <label key={key} className="space-y-2 text-sm font-medium">
      {label}
      <Input
        type={type}
        value={settingsJson[key] ?? String(settings[key] ?? "")}
        min={type === "number" ? 0 : undefined}
        step={type === "number" ? "any" : undefined}
        onChange={(event) => updateSettings(key, event.target.value)}
      />
    </label>
  );
  const optionField = (key: string, label: string, choices: string[]) => (
    <SelectField
      key={key}
      label={label}
      value={settingsJson[key] ?? String(settings[key] ?? choices[0])}
      options={choices.map((choice) => ({ value: choice, label: choice }))}
      onChange={(value) => updateSettings(key, value)}
    />
  );
  const labeledOptionField = (
    key: string,
    label: string,
    choices: { value: string; label: string }[],
  ) => (
    <SelectField
      key={key}
      label={label}
      value={settingsJson[key] ?? String(settings[key] ?? choices[0]?.value ?? "")}
      options={choices}
      onChange={(value) => updateSettings(key, value)}
    />
  );
  const jsonField = (key: string, label: string) => (
    <JsonEditor
      key={key}
      label={label}
      value={settingsJson[key] ?? settings[key]}
      onChange={(value) => updateSettings(key, value)}
    />
  );

  return (
    <Card className="panel-card mt-6">
      <CardHeader>
        <CardTitle className="font-display text-xl">Configuração visual e de combate</CardTitle>
        <CardDescription>
          Selecione uma entidade já cadastrada. Esta configuração estende o registro existente e não
          cria ficha, inventário ou sistema de recompensas paralelo.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {entities.isLoading ? (
          <p className="text-sm text-muted-foreground">Carregando entidades…</p>
        ) : entities.error ? (
          <p role="alert" className="text-sm text-destructive">
            Não foi possível carregar as entidades. {entities.error.message}
          </p>
        ) : (
          <div className="space-y-5">
            <SelectField
              label="Entidade"
              value={selectedId}
              options={[
                { value: "", label: "Selecione uma entidade existente" },
                ...(entities.data ?? []).map((entity) => ({
                  value: entity.id,
                  label: entity.name,
                })),
              ]}
              onChange={setSelectedId}
            />
            {supportingErrors.length > 0 && (
              <p role="alert" className="text-sm text-destructive">
                Não foi possível carregar todas as opções necessárias:{" "}
                {supportingErrors.map((error) => error.message).join(" ")}
              </p>
            )}
            {draft && selectedEntity && (
              <form className="space-y-5" onSubmit={submit}>
                {!activeProfile && profiles.data && profiles.data.length > 0 && (
                  <SelectField
                    label="Duplicar configuração existente"
                    value=""
                    options={[
                      { value: "", label: "Não duplicar" },
                      ...profiles.data.map((profile) => ({
                        value: profile.id,
                        label: `${
                          entities.data?.find((entity) => entity.id === profile.entity_id)?.name ??
                          profile.entity_id
                        } — ${profile.kind || "perfil"}`,
                      })),
                    ]}
                    onChange={duplicateProfile}
                  />
                )}
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <SelectField
                    label="Disponibilidade"
                    value={draft.availability}
                    options={[
                      { value: "draft", label: "Rascunho" },
                      { value: "available", label: "Disponível" },
                      { value: "archived", label: "Arquivado" },
                    ]}
                    onChange={(value) =>
                      updateDraft({ availability: value as ProfileAvailability })
                    }
                  />
                  <label className="space-y-2 text-sm font-medium">
                    Escala
                    <Input
                      type="number"
                      min={0.1}
                      max={5}
                      step="0.1"
                      value={draft.scale}
                      onChange={(event) => updateDraft({ scale: Number(event.target.value) })}
                    />
                  </label>
                  <SelectField
                    label="Orientação"
                    value={draft.orientation}
                    options={["auto", "left", "right"].map((value) => ({ value, label: value }))}
                    onChange={(value) =>
                      updateDraft({ orientation: value as EntityProfile["orientation"] })
                    }
                  />
                </div>

                <section className="space-y-3 rounded-xl border border-primary/25 bg-primary/5 p-4">
                  <div>
                    <h3 className="font-semibold">Animação de combate · até 2 GIFs</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      O GIF de execução identifica quem ataca; o GIF do projétil percorre a
                      distância até o alvo. São apenas visuais: o servidor calcula o dano.
                    </p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {[
                      { value: "attack" as const, label: "GIF de execução" },
                      { value: "impact" as const, label: "GIF do projétil" },
                    ].map(({ value, label }) => (
                      <div key={value} className="space-y-2">
                        <SelectField
                          label={label}
                          value={draft.assets.find((entry) => entry.role === value)?.asset_id ?? ""}
                          options={[
                            { value: "", label: "Sem GIF" },
                            ...(assets.data ?? [])
                              .filter((asset) => asset.content_type === "image/gif")
                              .map((asset) => ({ value: asset.id, label: asset.name })),
                          ]}
                          onChange={(assetId) =>
                            updateDraft({
                              assets: [
                                ...draft.assets.filter((entry) => entry.role !== value),
                                ...(assetId ? [{ role: value, asset_id: assetId }] : []),
                              ],
                            })
                          }
                        />
                        <label className="block space-y-2 text-xs text-muted-foreground">
                          Enviar um GIF novo (máx. 5 MB)
                          <Input
                            type="file"
                            accept="image/gif,.gif"
                            aria-label={`Enviar GIF de ${value === "attack" ? "execução" : "projétil"}`}
                            disabled={uploadingRole !== null}
                            onChange={(event) => {
                              const file = event.currentTarget.files?.[0];
                              event.currentTarget.value = "";
                              if (file) void uploadCombatGif(value, file);
                            }}
                          />
                        </label>
                        {uploadingRole === value && (
                          <p role="status" className="text-xs text-muted-foreground">
                            Enviando GIF…
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </section>

                <details className="rounded-lg border p-4">
                  <summary className="cursor-pointer font-semibold">
                    Assets e animações adicionais (opcional)
                  </summary>
                  <div className="mt-4 space-y-4">
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      {supplementaryAssetSlots.map(({ value, label }) => (
                        <SelectField
                          key={value}
                          label={label}
                          value={draft.assets.find((entry) => entry.role === value)?.asset_id ?? ""}
                          options={[
                            { value: "", label: "Não associado" },
                            ...(assets.data ?? [])
                              .filter((asset) => asset.content_type.startsWith("image/"))
                              .map((asset) => ({ value: asset.id, label: asset.name })),
                          ]}
                          onChange={(assetId) =>
                            updateDraft({
                              assets: [
                                ...draft.assets.filter((entry) => entry.role !== value),
                                ...(assetId ? [{ role: value, asset_id: assetId }] : []),
                              ],
                            })
                          }
                        />
                      ))}
                    </div>
                    <h3 className="font-semibold">Configurações de animação</h3>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      {animationSlots.map(({ value, label }) => (
                        <SelectField
                          key={value}
                          label={label}
                          value={
                            draft.animations.find((entry) => entry.role === value)?.animation_id ??
                            ""
                          }
                          options={[
                            { value: "", label: "Não associado" },
                            ...(animations.data ?? []).map((animation) => ({
                              value: animation.id,
                              label: animation.name,
                            })),
                          ]}
                          onChange={(animationId) =>
                            updateDraft({
                              animations: [
                                ...draft.animations.filter((entry) => entry.role !== value),
                                ...(animationId
                                  ? [{ role: value, animation_id: animationId }]
                                  : []),
                              ],
                            })
                          }
                        />
                      ))}
                    </div>
                  </div>
                </details>

                {(entityType === "enemy" || entityType === "npc") && (
                  <section className="space-y-3">
                    <h3 className="font-semibold">
                      {entityType === "enemy"
                        ? "Ataques disponíveis e velocidade"
                        : "Habilidades e velocidade por ataque"}
                    </h3>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {(skills.data ?? []).map((skill) => {
                        const association = draft.skills.find(
                          (entry) => entry.skill_id === skill.id,
                        );
                        return (
                          <label
                            key={skill.id}
                            className="flex flex-wrap items-center gap-3 rounded-md border border-border p-3 text-sm"
                          >
                            <input
                              type="checkbox"
                              checked={Boolean(association)}
                              onChange={(event) =>
                                updateDraft({
                                  skills: event.target.checked
                                    ? [
                                        ...draft.skills,
                                        { skill_id: skill.id, attack_speed_override: null },
                                      ]
                                    : draft.skills.filter((entry) => entry.skill_id !== skill.id),
                                })
                              }
                            />
                            <span className="min-w-24 flex-1">{skill.name}</span>
                            <Input
                              className="w-36"
                              type="number"
                              min={0.01}
                              max={100}
                              step="0.01"
                              aria-label={`Velocidade de ataque de ${skill.name}`}
                              placeholder="Padrão da entidade"
                              disabled={!association}
                              value={association?.attack_speed_override ?? ""}
                              onChange={(event) =>
                                updateDraft({
                                  skills: draft.skills.map((entry) =>
                                    entry.skill_id === skill.id
                                      ? {
                                          ...entry,
                                          attack_speed_override: event.target.value
                                            ? Number(event.target.value)
                                            : null,
                                        }
                                      : entry,
                                  ),
                                })
                              }
                            />
                          </label>
                        );
                      })}
                    </div>
                  </section>
                )}

                {entityType === "npc" && (
                  <section className="space-y-3">
                    <h3 className="font-semibold">Equipamentos associados</h3>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {(items.data ?? []).map((item) => (
                        <label key={item.id} className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={draft.equipment_ids.includes(item.id)}
                            onChange={(event) =>
                              updateDraft({
                                equipment_ids: event.target.checked
                                  ? [...draft.equipment_ids, item.id]
                                  : draft.equipment_ids.filter((id) => id !== item.id),
                              })
                            }
                          />
                          {item.name}
                        </label>
                      ))}
                    </div>
                  </section>
                )}

                <section className="space-y-3">
                  <h3 className="font-semibold">Configuração específica</h3>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {entityType === "npc" &&
                      optionField("actor_type", "Tipo de personagem", ["npc", "ally", "hostile"])}
                    {entityType === "enemy" && (
                      <>
                        {labeledOptionField("category", "Classe", [
                          { value: "common", label: "Inimigo" },
                          { value: "special", label: "Inimigo especial" },
                          { value: "miniboss", label: "Miniboss" },
                          { value: "boss", label: "Boss" },
                        ])}
                        {field("default_attack_speed", "Velocidade padrão de ataque", "number")}
                        {field("gold_reward", "Ouro concedido ao derrotar", "number")}
                        <p className="text-sm font-semibold sm:col-span-2 lg:col-span-3">
                          Comportamento do boss
                        </p>
                        {labeledOptionField("boss_difficulty", "Dificuldade", [
                          { value: "common", label: "FÁCIL" },
                          { value: "medium", label: "MÉDIO" },
                          { value: "difficult", label: "DIFÍCIL" },
                          { value: "hard", label: "HARD (legado)" },
                          { value: "impossible", label: "IMPOSSÍVEL" },
                        ])}
                        {labeledOptionField("max_attacks_per_turn", "Máximo de ataques por turno", [
                          { value: "1", label: "1" },
                          { value: "2", label: "2" },
                        ])}
                        {labeledOptionField("can_interrupt_turns", "Pode interromper turnos", [
                          { value: "false", label: "NÃO" },
                          { value: "true", label: "SIM" },
                        ])}
                        {optionField("strategy", "Estratégia/comportamento", [
                          "baseline",
                          "effective_damage",
                          "mana_conservation",
                          "focus_low_hp",
                          "elemental_weakness",
                          "aggressive",
                          "conservative",
                          "economic",
                          "tactical",
                          "adaptive",
                        ])}
                        {field(
                          "attack_release_delay_ms",
                          "Tempo até liberar ataque (ms)",
                          "number",
                        )}
                        {field(
                          "attack_animation_duration_ms",
                          "Duração da animação (ms)",
                          "number",
                        )}
                      </>
                    )}
                    {entityType === "item" && (
                      <>
                        {field("weapon_type", "Tipo de arma")}
                        {field("attack", "Ataque", "number")}
                        {field("defense", "Defesa", "number")}
                        {field("reach", "Alcance", "number")}
                        {field("speed", "Velocidade", "number")}
                        {optionField("animation_display", "Exibição na animação", [
                          "with_character",
                          "follow_character",
                          "during_strike",
                          "effect_only",
                        ])}
                      </>
                    )}
                    {entityType === "skill" && (
                      <>
                        {field("skill_type", "Tipo de habilidade")}
                        {field(
                          "damage_base",
                          "Dano base (opcional; substitui o cadastro)",
                          "number",
                        )}
                        {field("reach", "Alcance", "number")}
                        {field("target_type", "Tipo de alvo")}
                        {field("default_speed", "Velocidade", "number")}
                        {field(
                          "attack_release_delay_ms",
                          "Tempo até liberar ataque (ms)",
                          "number",
                        )}
                        {field(
                          "attack_animation_duration_ms",
                          "Duração da animação (ms)",
                          "number",
                        )}
                        {field("travel_duration_ms", "Duração do deslocamento (ms)", "number")}
                        {field("impact_time_ms", "Tempo de impacto (ms)", "number")}
                        {labeledOptionField("combat_visual_mode", "Uso dos GIFs", [
                          { value: "separated", label: "Execução e projétil em slots separados" },
                          { value: "legacy", label: "Legado: GIF de ataque é o projétil" },
                        ])}
                        {labeledOptionField("projectile_only", "Animação da habilidade", [
                          { value: "false", label: "Personagem e projétil" },
                          { value: "true", label: "Somente projétil" },
                        ])}
                        {optionField("trajectory", "Trajetória", trajectories)}
                        {optionField("direction", "Direção", [
                          "auto",
                          "left",
                          "right",
                          "up",
                          "down",
                        ])}
                      </>
                    )}
                    {entityType === "character" && (
                      <>
                        {field(
                          "attack_release_delay_ms",
                          "Tempo até liberar ataque (ms)",
                          "number",
                        )}
                        {field(
                          "attack_animation_duration_ms",
                          "Duração da animação (ms)",
                          "number",
                        )}
                      </>
                    )}
                  </div>
                  {entityType === "enemy" &&
                    jsonField("special_rewards", "Recompensas especiais (JSON)")}
                  {entityType === "item" &&
                    jsonField("special_effects", "Efeitos especiais (JSON)")}
                  {entityType === "skill" &&
                    jsonField("additional_effects", "Efeitos adicionais (JSON)")}
                  {entityType !== "character" && (
                    <JsonEditor
                      label="Atributos"
                      value={attributesJson}
                      onChange={setAttributesJson}
                    />
                  )}
                </section>

                {draft.default_position && (
                  <section className="space-y-3">
                    <h3 className="font-semibold">Posição padrão normalizada (0 a 1)</h3>
                    <div className="grid gap-4 sm:grid-cols-2">
                      {(["x", "y"] as const).map((axis) => (
                        <label key={axis} className="space-y-2 text-sm font-medium">
                          {axis.toUpperCase()}
                          <Input
                            type="number"
                            min={0}
                            max={1}
                            step="0.01"
                            value={draft.default_position[axis]}
                            onChange={(event) =>
                              updateDraft({
                                default_position: {
                                  ...draft.default_position,
                                  [axis]: Number(event.target.value),
                                },
                              })
                            }
                          />
                        </label>
                      ))}
                    </div>
                  </section>
                )}

                <div className="flex flex-wrap gap-3">
                  <Button type="submit" disabled={save.isPending || !dependenciesReady}>
                    {save.isPending
                      ? "Salvando…"
                      : activeProfile
                        ? "Salvar configuração"
                        : "Criar configuração"}
                  </Button>
                  {activeProfile && (
                    <ConfirmDialog
                      title="Excluir configuração visual?"
                      description="A configuração e suas associações serão removidas. A entidade base, sua ficha, inventário e campanha serão preservados."
                      confirmLabel="Excluir configuração"
                      onConfirm={() => remove.mutate()}
                      trigger={
                        <Button type="button" variant="destructive" disabled={remove.isPending}>
                          Excluir configuração
                        </Button>
                      }
                    />
                  )}
                </div>
              </form>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
