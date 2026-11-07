import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Check, Pencil, Plus, UserPlus } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/ui-bits";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { adminContentRequest } from "@/lib/admin-content-api";

type CampaignOption = { id: string; title: string };
type CatalogOption = { id: string; name: string };
type Objective = { id: string; title: string; description: string; target: number };
type Mission = {
  id: string;
  campaign_id: string;
  campaign_title: string;
  title: string;
  description: string;
  status: "draft" | "published" | "inactive";
  conditions: { objectives: Objective[]; require_all_objectives: boolean };
  rewards: {
    xp: number;
    gold: number;
    items: { item_id: string; quantity: number }[];
    skill_ids: string[];
  };
  assignments: {
    character_id: string;
    character_name: string;
    status: string;
    progress: Record<string, unknown>;
    objectives: Objective[];
  }[];
};
type Target = { id: string; name: string; level: number; player_name: string };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseRecords(value: unknown, label: string): Record<string, unknown>[] {
  if (!Array.isArray(value) || !value.every(isRecord))
    throw new Error(`A API retornou uma lista inválida de ${label}.`);
  return value;
}

function parseMissions(value: unknown): Mission[] {
  return parseRecords(value, "missões").map((row) => {
    const conditions = isRecord(row["conditions"]) ? row["conditions"] : {};
    const rewards = isRecord(row["rewards"]) ? row["rewards"] : {};
    const rawAssignments = Array.isArray(row["assignments"]) ? row["assignments"] : [];
    const assignments = rawAssignments.flatMap((entry) => {
      if (!isRecord(entry)) return [];
      const { character_id, character_name, status, progress } = entry;
      if (
        typeof character_id !== "string" ||
        typeof character_name !== "string" ||
        typeof status !== "string" ||
        !isRecord(progress)
      )
        return [];
      const objectives = Array.isArray(entry["objectives"])
        ? entry["objectives"].flatMap((rawObjective) => {
            if (!isRecord(rawObjective)) return [];
            const { id, title, description, target } = rawObjective;
            return typeof id === "string" &&
              typeof title === "string" &&
              typeof description === "string" &&
              typeof target === "number"
              ? [{ id, title, description, target }]
              : [];
          })
        : [];
      return [{ character_id, character_name, status, progress, objectives }];
    });
    const objectives = Array.isArray(conditions["objectives"])
      ? conditions["objectives"].flatMap((entry) => {
          if (!isRecord(entry)) return [];
          const { id, title, description, target } = entry;
          if (
            typeof id !== "string" ||
            typeof title !== "string" ||
            typeof description !== "string" ||
            typeof target !== "number"
          )
            return [];
          return [{ id, title, description, target }];
        })
      : [];
    const items = Array.isArray(rewards["items"])
      ? rewards["items"].flatMap((entry) => {
          if (!isRecord(entry)) return [];
          const { item_id, quantity } = entry;
          return typeof item_id === "string" && typeof quantity === "number"
            ? [{ item_id, quantity }]
            : [];
        })
      : [];
    const rawStatus = row["status"];
    const normalizedStatus =
      rawStatus === "publicado" || rawStatus === "active"
        ? "published"
        : rawStatus === "rascunho"
          ? "draft"
          : rawStatus;
    if (
      typeof row["id"] !== "string" ||
      typeof row["campaign_id"] !== "string" ||
      typeof row["campaign_title"] !== "string" ||
      typeof row["title"] !== "string" ||
      typeof row["description"] !== "string" ||
      !["draft", "published", "inactive"].includes(String(normalizedStatus))
    )
      throw new Error("A API retornou uma missão em formato inesperado.");
    return {
      id: row["id"],
      campaign_id: row["campaign_id"],
      campaign_title: row["campaign_title"],
      title: row["title"],
      description: row["description"],
      status: normalizedStatus as Mission["status"],
      conditions: {
        objectives,
        require_all_objectives: conditions["require_all_objectives"] !== false,
      },
      rewards: {
        xp: typeof rewards["xp"] === "number" ? rewards["xp"] : 0,
        gold: typeof rewards["gold"] === "number" ? rewards["gold"] : 0,
        items,
        skill_ids: Array.isArray(rewards["skill_ids"])
          ? rewards["skill_ids"].filter((id): id is string => typeof id === "string")
          : [],
      },
      assignments,
    };
  });
}

function parseCampaigns(value: unknown): CampaignOption[] {
  return parseRecords(value, "campanhas").flatMap((row) =>
    typeof row["id"] === "string" && typeof row["title"] === "string"
      ? [{ id: row["id"], title: row["title"] }]
      : [],
  );
}

function parseCatalog(value: unknown, label: string): CatalogOption[] {
  return parseRecords(value, label).flatMap((row) =>
    typeof row["id"] === "string" && typeof row["name"] === "string"
      ? [{ id: row["id"], name: row["name"] }]
      : [],
  );
}

function parseTargets(value: unknown): Target[] {
  return parseRecords(value, "personagens").flatMap((row) =>
    typeof row["id"] === "string" &&
    typeof row["name"] === "string" &&
    typeof row["level"] === "number" &&
    typeof row["player_name"] === "string"
      ? [{ id: row["id"], name: row["name"], level: row["level"], player_name: row["player_name"] }]
      : [],
  );
}

function objectiveLines(objectives: Objective[]): string {
  return objectives
    .map((objective) =>
      [objective.id, objective.title, objective.description, objective.target].join(" | "),
    )
    .join("\n");
}

export function MissionManagementPage() {
  const queryClient = useQueryClient();
  const missionsQuery = useQuery({
    queryKey: ["admin-content", "quests"],
    queryFn: async () => parseMissions(await adminContentRequest("/api/admin/content/quests")),
  });
  const campaignsQuery = useQuery({
    queryKey: ["admin-content", "campaigns"],
    queryFn: async () => parseCampaigns(await adminContentRequest("/api/admin/content/campaigns")),
  });
  const itemsQuery = useQuery({
    queryKey: ["admin-content", "items"],
    queryFn: async () =>
      parseCatalog(await adminContentRequest("/api/admin/content/items"), "itens"),
  });
  const skillsQuery = useQuery({
    queryKey: ["admin-content", "skills"],
    queryFn: async () =>
      parseCatalog(await adminContentRequest("/api/admin/content/skills"), "habilidades"),
  });
  const missions = missionsQuery.data ?? [];
  const campaigns = campaignsQuery.data ?? [];
  const items = itemsQuery.data ?? [];
  const skills = skillsQuery.data ?? [];

  const [selectedId, setSelectedId] = useState("");
  const selectedMission = missions.find((mission) => mission.id === selectedId);
  const [campaignId, setCampaignId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<Mission["status"]>("draft");
  const [objectivesText, setObjectivesText] = useState("");
  const [requireAll, setRequireAll] = useState(true);
  const [xp, setXp] = useState("0");
  const [gold, setGold] = useState("0");
  const [itemIds, setItemIds] = useState<string[]>([]);
  const [skillIds, setSkillIds] = useState<string[]>([]);
  const [assignMissionId, setAssignMissionId] = useState("");
  const [targetIds, setTargetIds] = useState<string[]>([]);
  const [assignCampaignId, setAssignCampaignId] = useState("");

  const targetsQuery = useQuery({
    queryKey: ["admin-content", "quest-targets", assignCampaignId],
    enabled: Boolean(assignCampaignId),
    queryFn: async () =>
      parseTargets(
        await adminContentRequest(
          `/api/admin/content/quests/targets?campaign_id=${encodeURIComponent(assignCampaignId)}`,
        ),
      ),
  });
  const targets = targetsQuery.data ?? [];

  function resetForm() {
    setSelectedId("");
    setCampaignId(campaigns[0]?.id ?? "");
    setTitle("");
    setDescription("");
    setStatus("draft");
    setObjectivesText("");
    setRequireAll(true);
    setXp("0");
    setGold("0");
    setItemIds([]);
    setSkillIds([]);
  }

  function editMission(mission: Mission) {
    setSelectedId(mission.id);
    setCampaignId(mission.campaign_id);
    setTitle(mission.title);
    setDescription(mission.description);
    setStatus(mission.status);
    setObjectivesText(objectiveLines(mission.conditions.objectives));
    setRequireAll(mission.conditions.require_all_objectives);
    setXp(String(mission.rewards.xp));
    setGold(String(mission.rewards.gold));
    setItemIds(mission.rewards.items.map((item) => item.item_id));
    setSkillIds(mission.rewards.skill_ids);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const missionPayload = useMemo(
    () => ({
      campaign_id: campaignId,
      title: title.trim(),
      description: description.trim(),
      status,
      conditions: {
        objectives: objectivesText
          .split("\n")
          .filter((line) => line.trim())
          .map((line) => {
            const [id = "", objectiveTitle = "", objectiveDescription = "", targetText = "1"] = line
              .split("|")
              .map((part) => part.trim());
            return {
              id,
              title: objectiveTitle,
              description: objectiveDescription,
              target: Number(targetText),
            };
          }),
        require_all_objectives: requireAll,
      },
      rewards: {
        xp: Number(xp),
        gold: Number(gold),
        items: itemIds.map((item_id) => ({ item_id, quantity: 1 })),
        skill_ids: skillIds,
      },
    }),
    [
      campaignId,
      description,
      itemIds,
      objectivesText,
      requireAll,
      skillIds,
      status,
      title,
      xp,
      gold,
    ],
  );

  const saveMutation = useMutation({
    mutationFn: () =>
      adminContentRequest(
        selectedId ? `/api/admin/content/quests/${selectedId}` : "/api/admin/content/quests",
        selectedId ? "PUT" : "POST",
        missionPayload,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-content", "quests"] });
      toast.success(selectedId ? "Missão atualizada." : "Missão criada.");
      resetForm();
    },
    onError: (error) =>
      toast.error("Não foi possível salvar a missão.", {
        description: error instanceof Error ? error.message : String(error),
      }),
  });

  const assignMutation = useMutation({
    mutationFn: () =>
      adminContentRequest(`/api/admin/content/quests/${assignMissionId}/assign`, "POST", {
        character_ids: targetIds,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-content", "quests"] });
      toast.success("Missão atribuída aos personagens selecionados.");
      setTargetIds([]);
    },
    onError: (error) =>
      toast.error("Não foi possível atribuir a missão.", {
        description: error instanceof Error ? error.message : String(error),
      }),
  });

  function toggle(values: string[], setValues: (next: string[]) => void, id: string) {
    setValues(values.includes(id) ? values.filter((value) => value !== id) : [...values, id]);
  }

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      if (!campaignId) throw new Error("Selecione a campanha da missão.");
      if (!Number.isSafeInteger(Number(xp)) || Number(xp) < 0) throw new Error("XP inválido.");
      if (!Number.isSafeInteger(Number(gold)) || Number(gold) < 0)
        throw new Error("Quantidade de ouro inválida.");
      const ids = new Set<string>();
      for (const objective of missionPayload.conditions.objectives) {
        if (
          !objective.id ||
          !objective.title ||
          !Number.isSafeInteger(objective.target) ||
          objective.target < 1
        )
          throw new Error("Objetivos usem id | título | descrição | meta (meta inteira positiva).");
        if (ids.has(objective.id)) throw new Error("Os IDs dos objetivos devem ser únicos.");
        ids.add(objective.id);
      }
      if (!title.trim()) throw new Error("Informe o título da missão.");
      saveMutation.mutate();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Gestão de missões"
        description="Edite objetivos e recompensas, publique missões e atribua-as a personagens ativos da campanha."
      />

      <Card className="border-primary/25 bg-primary/5">
        <CardHeader>
          <CardTitle className="text-base">Como as missões funcionam hoje</CardTitle>
          <CardDescription>
            Missão principal e secundária usam o mesmo cadastro; “secundária” é uma forma de
            organizar a história, não um tipo automático do sistema.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            Publique a missão e atribua-a aos personagens pela seção de atribuição abaixo. Defina
            cada objetivo com um ID único, uma meta e escolha se todos os objetivos ou apenas um
            precisam ser concluídos.
          </p>
          <p>
            Atualmente, o progresso é atualizado quando uma escolha narrativa vinculada avança um
            objetivo ou conclui a missão. Derrotar um inimigo, coletar um item ou vencer um combate
            ainda não atualiza objetivos automaticamente.
          </p>
          <p>
            Sugestão para a próxima etapa: adicionar gatilhos de objetivo (“derrotar criatura”,
            “obter item”, “visitar cena” ou “escolha narrativa”), indicar se a missão é principal ou
            secundária e deixar claro se a recompensa é individual ou compartilhada pelo grupo.
          </p>
        </CardContent>
      </Card>

      <Card className="panel-card">
        <CardHeader>
          <CardTitle className="font-display text-xl">
            {selectedId ? "Editar missão" : "Criar missão"}
          </CardTitle>
          <CardDescription>
            A conclusão é validada pelo backend. As recompensas usam XP, ouro, itens e habilidades
            do catálogo oficial. O progresso ocorre apenas pelos gatilhos narrativos atualmente
            suportados.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2 text-sm font-medium">
              Campanha
              <select
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={campaignId}
                onChange={(event) => setCampaignId(event.target.value)}
                required
              >
                <option value="">Selecione</option>
                {campaigns.map((campaign) => (
                  <option key={campaign.id} value={campaign.id}>
                    {campaign.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-2 text-sm font-medium">
              Publicação
              <select
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={status}
                onChange={(event) => setStatus(event.target.value as Mission["status"])}
              >
                <option value="draft">Rascunho</option>
                <option value="published">Publicada</option>
                <option value="inactive">Despublicada</option>
              </select>
            </label>
            <label className="space-y-2 text-sm font-medium md:col-span-2">
              Título
              <Input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                maxLength={160}
                required
              />
            </label>
            <label className="space-y-2 text-sm font-medium md:col-span-2">
              Descrição
              <Textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={3}
              />
            </label>
            <label className="space-y-2 text-sm font-medium md:col-span-2">
              Objetivos (um por linha: ID único | título | descrição | meta)
              <Textarea
                value={objectivesText}
                onChange={(event) => setObjectivesText(event.target.value)}
                placeholder={"encontrar-chave | Encontrar a chave | Procure na torre | 1"}
                rows={4}
              />
            </label>
            <label className="flex items-center gap-2 text-sm md:col-span-2">
              <input
                type="checkbox"
                checked={requireAll}
                onChange={(event) => setRequireAll(event.target.checked)}
              />
              Exigir todos os objetivos para conclusão (desmarcado: basta um)
            </label>
            <label className="space-y-2 text-sm font-medium">
              Recompensa de XP
              <Input
                type="number"
                min={0}
                step={1}
                value={xp}
                onChange={(event) => setXp(event.target.value)}
              />
            </label>
            <label className="space-y-2 text-sm font-medium">
              Recompensa em ouro
              <Input
                type="number"
                min={0}
                step={1}
                value={gold}
                onChange={(event) => setGold(event.target.value)}
              />
            </label>
            <fieldset className="space-y-2 md:col-span-2">
              <legend className="mb-2 text-sm font-medium">Itens</legend>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {items.map((item) => (
                  <label key={item.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={itemIds.includes(item.id)}
                      onChange={() => toggle(itemIds, setItemIds, item.id)}
                    />
                    {item.name}
                  </label>
                ))}
              </div>
            </fieldset>
            <fieldset className="space-y-2 md:col-span-2">
              <legend className="mb-2 text-sm font-medium">Habilidades concedidas</legend>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {skills.map((skill) => (
                  <label key={skill.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={skillIds.includes(skill.id)}
                      onChange={() => toggle(skillIds, setSkillIds, skill.id)}
                    />
                    {skill.name}
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="flex flex-wrap gap-2 md:col-span-2">
              <Button type="submit" disabled={saveMutation.isPending || campaignsQuery.isLoading}>
                {saveMutation.isPending
                  ? "Salvando..."
                  : selectedId
                    ? "Salvar alterações"
                    : "Criar missão"}
              </Button>
              {selectedId && (
                <Button type="button" variant="outline" onClick={resetForm}>
                  Cancelar edição
                </Button>
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      {missionsQuery.isLoading ? (
        <p role="status" className="py-8 text-center text-sm text-muted-foreground">
          Carregando missões…
        </p>
      ) : missionsQuery.error ? (
        <p
          role="alert"
          className="rounded-lg border border-destructive/30 p-4 text-sm text-destructive"
        >
          Não foi possível carregar as missões. {missionsQuery.error.message}
        </p>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {missions.length === 0 && (
            <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground xl:col-span-2">
              Nenhuma missão cadastrada.
            </p>
          )}
          {missions.map((mission) => (
            <Card key={mission.id} className="panel-card">
              <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <CardTitle className="inline-flex items-center gap-2 font-display text-lg">
                    <BookOpen className="size-4 text-primary" /> {mission.title}
                  </CardTitle>
                  <CardDescription className="mt-1">{mission.campaign_title}</CardDescription>
                </div>
                <Badge variant="outline">
                  {mission.status === "published"
                    ? "Publicada"
                    : mission.status === "inactive"
                      ? "Despublicada"
                      : "Rascunho"}
                </Badge>
              </CardHeader>
              <CardContent className="space-y-4">
                {mission.description && (
                  <p className="text-sm leading-6 text-muted-foreground">{mission.description}</p>
                )}
                <p className="text-xs text-muted-foreground">
                  {mission.conditions.objectives.length} objetivos · {mission.rewards.xp} XP ·{" "}
                  {mission.rewards.gold} ouro
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => editMission(mission)}>
                    <Pencil className="mr-1 size-4" /> Editar / publicar
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={mission.status !== "published"}
                    onClick={() => {
                      setAssignMissionId(assignMissionId === mission.id ? "" : mission.id);
                      setAssignCampaignId(mission.campaign_id);
                      setTargetIds([]);
                    }}
                  >
                    <UserPlus className="mr-1 size-4" /> Atribuir
                  </Button>
                </div>
                {assignMissionId === mission.id && assignCampaignId === mission.campaign_id && (
                  <section className="rounded-lg border p-3" aria-label="Atribuição da missão">
                    <h3 className="mb-2 text-sm font-semibold">Personagens ativos da campanha</h3>
                    {targetsQuery.isLoading ? (
                      <p role="status" className="text-sm text-muted-foreground">
                        Carregando personagens…
                      </p>
                    ) : targetsQuery.error ? (
                      <p role="alert" className="text-sm text-destructive">
                        {targetsQuery.error.message}
                      </p>
                    ) : targets.length === 0 ? (
                      <p className="text-sm text-muted-foreground">
                        Não há personagens ativos vinculados.
                      </p>
                    ) : (
                      <div className="grid gap-2 sm:grid-cols-2">
                        {targets.map((target) => (
                          <label key={target.id} className="flex items-center gap-2 text-sm">
                            <input
                              type="checkbox"
                              checked={targetIds.includes(target.id)}
                              onChange={() => toggle(targetIds, setTargetIds, target.id)}
                            />
                            <span>
                              {target.name} · nível {target.level}
                              <span className="block text-xs text-muted-foreground">
                                {target.player_name}
                              </span>
                            </span>
                          </label>
                        ))}
                      </div>
                    )}
                    <Button
                      className="mt-3"
                      size="sm"
                      disabled={targetIds.length === 0 || assignMutation.isPending}
                      onClick={() => assignMutation.mutate()}
                    >
                      <Check className="mr-1 size-4" /> Atribuir selecionados
                    </Button>
                  </section>
                )}
                <div className="border-t pt-3">
                  <h3 className="mb-2 text-sm font-semibold">Atribuições e estado</h3>
                  {mission.assignments.length === 0 ? (
                    <p className="text-xs text-muted-foreground">Ainda sem atribuições.</p>
                  ) : (
                    <ul className="space-y-1 text-sm">
                      {mission.assignments.map((assignment) => {
                        const rawProgress = assignment.progress["objectives"];
                        const objectiveProgress = isRecord(rawProgress) ? rawProgress : {};
                        const progressText = assignment.objectives
                          .map((objective) => {
                            const count = objectiveProgress[objective.id];
                            return `${objective.title} ${typeof count === "number" ? Math.min(count, objective.target) : 0}/${objective.target}`;
                          })
                          .join(" · ");
                        return (
                          <li
                            key={assignment.character_id}
                            className="flex flex-wrap justify-between gap-2"
                          >
                            <span>
                              {assignment.character_name}
                              {progressText && (
                                <span className="block text-xs text-muted-foreground">
                                  {progressText}
                                </span>
                              )}
                            </span>
                            <span className="text-xs capitalize text-muted-foreground">
                              {assignment.status.replaceAll("_", " ")}
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      {!campaignsQuery.isLoading && campaignsQuery.error && (
        <p role="alert" className="text-sm text-destructive">
          Não foi possível carregar campanhas: {campaignsQuery.error.message}
        </p>
      )}
      {!itemsQuery.isLoading && itemsQuery.error && (
        <p role="alert" className="text-sm text-destructive">
          Não foi possível carregar o catálogo de itens: {itemsQuery.error.message}
        </p>
      )}
      {!skillsQuery.isLoading && skillsQuery.error && (
        <p role="alert" className="text-sm text-destructive">
          Não foi possível carregar o catálogo de habilidades: {skillsQuery.error.message}
        </p>
      )}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Plus className="size-3" /> Objetivos só avançam por eventos narrativos autoritativos, não
        por ações do cliente.
      </div>
    </div>
  );
}
