import { useMemo, useState } from "react";
import { BookOpen, ChevronDown, ChevronUp, Pencil, Plus, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CrudPage, type Column } from "@/components/common/CrudPage";
import { EntityFormDialog, type FieldDef } from "@/components/common/EntityForm";
import { ConfirmDialog, PageHeader } from "@/components/common/ui-bits";
import { useCollection, useSaveEntity } from "@/hooks/use-collection";
import { newId } from "@/services/dataService";
import type { Chapter, Choice, Dialogue, Scene } from "@/types/entities";

type SceneFormValues = {
  title: string;
  narrative: string;
  dialogues: string[];
  choices: string[];
  npcIds: string[];
  enemyIds: string[];
  conditions: string;
  isActive: boolean;
};

const chapterFields: FieldDef[] = [
  { name: "order", label: "Ordem", type: "number", min: 1 },
  { name: "title", label: "Título", type: "text", required: true },
  { name: "summary", label: "Resumo", type: "textarea", full: true },
  { name: "narrative", label: "Texto narrativo", type: "textarea", full: true },
  {
    name: "status",
    label: "Status",
    type: "select",
    options: [
      { value: "rascunho", label: "Rascunho" },
      { value: "publicado", label: "Publicado" },
    ],
  },
  { name: "isActive", label: "Capítulo ativo", type: "checkbox" },
  { name: "npcIds", label: "NPCs associados", type: "multi", options: [] },
  { name: "encounterIds", label: "Encontros com monstros", type: "multi", options: [] },
];

const sceneFields: FieldDef[] = [
  { name: "title", label: "Nome da cena", type: "text", required: true },
  { name: "narrative", label: "Texto narrativo", type: "textarea", full: true },
  {
    name: "dialogues",
    label: "Diálogos (um por linha, no formato personagem | fala)",
    type: "list",
    full: true,
    placeholder: "Mercador | Alguém a detenha!",
  },
  {
    name: "choices",
    label:
      "Opções (uma por linha: texto | ID da próxima cena ou vazio | condição informativa | consequência | UUIDs de recompensas | UUIDs de missões concluídas | avanços questUUID:objectiveID:quantidade)",
    type: "list",
    full: true,
    placeholder:
      "Ajudar o mercador | ID da cena destino ou vazio | carisma >= 5 | Ajudou o mercador | UUIDs de recompensas | UUIDs de missões concluídas | questUUID:objectiveID:1",
  },
  { name: "npcIds", label: "NPCs nesta cena", type: "multi", options: [] },
  { name: "enemyIds", label: "Monstros e encontros", type: "multi", options: [] },
  { name: "conditions", label: "Condições para desbloquear", type: "textarea", full: true },
  { name: "isActive", label: "Cena ativa", type: "checkbox" },
];

function fromScene(scene: Scene): SceneFormValues {
  return {
    title: scene.title,
    narrative: scene.narrative,
    dialogues: scene.dialogues.map((dialogue) => `${dialogue.speaker} | ${dialogue.line}`),
    choices: scene.choices.map(
      (choice) =>
        `${choice.label} | ${choice.nextSceneId} | ${choice.condition} | ${choice.effect} | ${(choice.rewardIds ?? []).join(", ")} | ${(choice.questIds ?? []).join(", ")} | ${(choice.questObjectiveUpdates ?? []).map((update) => `${update.questId}:${update.objectiveId}:${update.amount}`).join(", ")}`,
    ),
    npcIds: scene.npcIds ?? [],
    enemyIds: scene.enemyIds ?? [],
    conditions: scene.conditions ?? "",
    isActive: scene.isActive ?? true,
  };
}

function toScene(values: Record<string, unknown>, existing?: Scene): Scene {
  const dialogues = (values["dialogues"] as string[]).map((line, index) => {
    const [speaker = "", ...parts] = line.split("|").map((part) => part.trim());
    const prior = existing?.dialogues[index];
    return {
      id: prior?.id ?? newId("dlg"),
      speaker,
      line: parts.join("|").trim(),
    } satisfies Dialogue;
  });
  const choices = (values["choices"] as string[]).map((line, index) => {
    const [
      label = "",
      nextSceneId = "",
      condition = "",
      effect = "",
      rewardIds = "",
      questIds = "",
      objectiveUpdates = "",
    ] = line.split("|").map((part) => part.trim());
    const prior = existing?.choices[index];
    return {
      id: prior?.id ?? newId("chc"),
      label,
      nextSceneId,
      condition,
      effect,
      rewardIds: rewardIds
        .split(",")
        .map((rewardId) => rewardId.trim())
        .filter(Boolean),
      questIds: questIds
        .split(",")
        .map((questId) => questId.trim())
        .filter(Boolean),
      questObjectiveUpdates: objectiveUpdates
        .split(",")
        .map((update) => {
          const [questId = "", objectiveId = "", amountText = "1"] = update.trim().split(":");
          return {
            questId,
            objectiveId,
            amount: Number(amountText),
          };
        })
        .filter((update) => update.questId && update.objectiveId),
    } satisfies Choice;
  });
  return {
    id: existing?.id ?? newId("scn"),
    title: String(values["title"] ?? "").trim(),
    narrative: String(values["narrative"] ?? "").trim(),
    dialogues,
    choices,
    npcIds: (values["npcIds"] as string[]) ?? [],
    enemyIds: (values["enemyIds"] as string[]) ?? [],
    conditions: String(values["conditions"] ?? "").trim(),
    isActive: Boolean(values["isActive"]),
  };
}

function sceneFormError(values: Record<string, unknown>): string | null {
  const invalidDialogue = (values["dialogues"] as string[]).some((line) => !line.includes("|"));
  if (invalidDialogue)
    return "Cada diálogo deve conter o nome do personagem e a fala separados por |.";
  const invalidChoice = (values["choices"] as string[]).some((line) => line.split("|").length < 4);
  if (invalidChoice)
    return "Cada opção deve conter texto, ID de destino, condição e consequência separados por |.";
  return null;
}

export function StoryPage() {
  const {
    data: chapters = [],
    isLoading: chaptersLoading,
    error: chaptersError,
  } = useCollection("chapters");
  const { data: npcs = [], error: npcsError } = useCollection("npcs");
  const { data: monsters = [], error: monstersError } = useCollection("monsters");
  const { data: availableRewards = [], error: rewardsError } = useCollection("questRewards");
  const saveChapter = useSaveEntity("chapters");
  const [selectedChapterId, setSelectedChapterId] = useState<string>("");
  const [editorScene, setEditorScene] = useState<Scene | null>(null);
  const [sceneDialogOpen, setSceneDialogOpen] = useState(false);

  const selectedChapter =
    chapters.find((chapter) => chapter.id === selectedChapterId) ?? chapters[0];
  const chapterColumns = useMemo<Column<Chapter>[]>(
    () => [
      { key: "order", label: "Ordem" },
      { key: "title", label: "Capítulo" },
      {
        key: "status",
        label: "Status",
        render: (chapter) => (
          <Badge variant="outline">
            {chapter.status === "publicado" ? "Publicado" : "Rascunho"}
          </Badge>
        ),
      },
      { key: "scenes", label: "Cenas", render: (chapter) => String(chapter.scenes.length) },
    ],
    [],
  );
  const fields = useMemo(
    () =>
      chapterFields.map((field) => {
        if (field.name === "npcIds" && field.type === "multi")
          return { ...field, options: npcs.map((npc) => ({ value: npc.id, label: npc.name })) };
        if (field.name === "encounterIds" && field.type === "multi")
          return {
            ...field,
            options: monsters.map((monster) => ({ value: monster.id, label: monster.name })),
          };
        return field;
      }),
    [monsters, npcs],
  );
  const sceneFormFields = useMemo(
    () =>
      sceneFields.map((field) => {
        if (field.name === "npcIds" && field.type === "multi")
          return { ...field, options: npcs.map((npc) => ({ value: npc.id, label: npc.name })) };
        if (field.name === "enemyIds" && field.type === "multi")
          return {
            ...field,
            options: monsters.map((monster) => ({ value: monster.id, label: monster.name })),
          };
        return field;
      }),
    [monsters, npcs],
  );
  const initialScene: SceneFormValues = editorScene
    ? fromScene(editorScene)
    : {
        title: "",
        narrative: "",
        dialogues: [],
        choices: [],
        npcIds: [],
        enemyIds: [],
        conditions: "",
        isActive: true,
      };

  function openSceneEditor(scene?: Scene) {
    setEditorScene(scene ?? null);
    setSceneDialogOpen(true);
  }

  async function saveScene(values: Record<string, unknown>) {
    if (!selectedChapter) return;
    const nextScene = toScene(values, editorScene ?? undefined);
    const scenes = editorScene
      ? selectedChapter.scenes.map((scene) => (scene.id === editorScene.id ? nextScene : scene))
      : [...selectedChapter.scenes, nextScene];
    await saveChapter.mutateAsync({ ...selectedChapter, scenes });
    setSceneDialogOpen(false);
    setEditorScene(null);
  }

  function moveScene(index: number, offset: -1 | 1) {
    if (!selectedChapter) return;
    const target = index + offset;
    if (target < 0 || target >= selectedChapter.scenes.length) return;
    const scenes = [...selectedChapter.scenes];
    const currentScene = scenes[index];
    const targetScene = scenes[target];
    if (!currentScene || !targetScene) return;
    scenes[index] = targetScene;
    scenes[target] = currentScene;
    saveChapter.mutate({ ...selectedChapter, scenes });
  }

  function deleteScene(sceneId: string) {
    if (!selectedChapter) return;
    saveChapter.mutate({
      ...selectedChapter,
      scenes: selectedChapter.scenes.filter((scene) => scene.id !== sceneId),
    });
  }

  return (
    <section>
      <PageHeader
        title="História e capítulos"
        description="Construa a narrativa, cenas, diálogos e escolhas da campanha."
        icon={BookOpen}
      />
      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <article className="rounded-xl border border-primary/25 bg-primary/5 p-4 sm:p-5">
          <h2 className="font-semibold">Como as escolhas conduzem a campanha</h2>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-muted-foreground">
            <li>Ao iniciar, a campanha usa a primeira cena ativa de um capítulo publicado.</li>
            <li>
              Cada participante elegível vota em uma opção. A decisão é fechada quando todos votam
              ou quando vence o prazo configurado na campanha.
            </li>
            <li>
              A opção vencedora aplica suas consequências e abre outra votação. Um empate sem regra
              de desempate ou uma votação sem votos não avança a história hoje.
            </li>
            <li>
              Um destino preenchido leva a uma cena do mesmo capítulo. Sem destino, a progressão
              segue a ordem das cenas e depois o próximo capítulo publicado.
            </li>
          </ol>
        </article>
        <article className="rounded-xl border p-4 sm:p-5">
          <h2 className="font-semibold">Fim do capítulo e recomendações</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Não existe um objetivo de conclusão separado por capítulo. Hoje, a sessão termina quando
            a campanha chega ao fim da última cena do último capítulo publicado; uma cena sem
            escolhas também encerra a progressão.
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            Sugestão: marque o encerramento com uma última cena e uma escolha final explícita.
            Configure prazo de votação para evitar espera infinita e prefira desempate por ordem ou,
            futuramente, uma rodada de desempate com as opções empatadas.
          </p>
        </article>
      </div>
      <div className="mb-6 rounded-xl border border-border bg-card/70 p-4 sm:p-5">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-display text-xl">Sequência de cenas</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Ordene as cenas e defina falas, destinos, condições e consequências.
            </p>
          </div>
          {(chaptersError || npcsError || monstersError || rewardsError) && (
            <p
              role="alert"
              className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
            >
              Não foi possível carregar todo o conteúdo oficial da história ou os modelos de
              recompensa. Verifique a sessão administrativa e a API; os dados locais de demonstração
              não serão usados como substitutos.
            </p>
          )}
          {chaptersLoading && (
            <p className="mb-4 text-sm text-muted-foreground">Carregando capítulos do servidor…</p>
          )}
          <div className="flex flex-col gap-2 sm:flex-row">
            <Select value={selectedChapter?.id ?? ""} onValueChange={setSelectedChapterId}>
              <SelectTrigger className="w-full sm:w-64" aria-label="Selecionar capítulo">
                <SelectValue placeholder="Selecione um capítulo" />
              </SelectTrigger>
              <SelectContent>
                {chapters.map((chapter) => (
                  <SelectItem key={chapter.id} value={chapter.id}>
                    {chapter.order}. {chapter.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button onClick={() => openSceneEditor()} disabled={!selectedChapter}>
              <Plus className="h-4 w-4" />
              Nova cena
            </Button>
          </div>
        </div>
        {(chaptersLoading || chaptersError) && !selectedChapter ? null : selectedChapter ? (
          selectedChapter.scenes.length ? (
            <ol className="space-y-3">
              {selectedChapter.scenes.map((scene, index) => (
                <li key={scene.id} className="rounded-lg border border-border bg-background/50 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/15 text-xs text-primary">
                          {index + 1}
                        </span>
                        <h3 className="font-medium">{scene.title}</h3>
                      </div>
                      <p className="mt-1 pl-8 font-mono text-[10px] text-muted-foreground/70">
                        ID: {scene.id}
                      </p>
                      <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                        {scene.narrative || "Sem texto narrativo."}
                      </p>
                      <p className="mt-2 text-xs text-muted-foreground">
                        {scene.dialogues.length} diálogo(s) · {scene.choices.length} escolha(s)
                      </p>
                    </div>
                    <div className="flex items-center">
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label="Mover cena para cima"
                        disabled={index === 0}
                        onClick={() => moveScene(index, -1)}
                      >
                        <ChevronUp className="h-4 w-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label="Mover cena para baixo"
                        disabled={index === selectedChapter.scenes.length - 1}
                        onClick={() => moveScene(index, 1)}
                      >
                        <ChevronDown className="h-4 w-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label="Editar cena"
                        onClick={() => openSceneEditor(scene)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <ConfirmDialog
                        title="Excluir cena?"
                        description="A cena será removida deste capítulo. Escolhas que apontam para ela não serão alteradas automaticamente."
                        confirmLabel="Excluir cena"
                        onConfirm={() => deleteScene(scene.id)}
                        trigger={
                          <Button size="icon" variant="ghost" aria-label="Excluir cena">
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        }
                      />
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
              Este capítulo ainda não tem cenas.
            </p>
          )
        ) : (
          <p className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
            Cadastre um capítulo para começar a estruturar sua história.
          </p>
        )}
      </div>

      <CrudPage
        collection="chapters"
        title="Capítulos"
        description="Edite resumos, narrativa, estado de publicação, NPCs e encontros associados."
        icon={BookOpen}
        entityLabel="capítulo"
        columns={chapterColumns}
        fields={fields}
        defaults={() => ({
          order: chapters.length + 1,
          title: "",
          summary: "",
          narrative: "",
          status: "rascunho",
          isActive: true,
          scenes: [],
          npcIds: [],
          encounterIds: [],
        })}
        searchKeys={["title", "summary", "narrative"]}
        filter={{
          key: "status",
          label: "Status",
          options: [
            { value: "rascunho", label: "Rascunho" },
            { value: "publicado", label: "Publicado" },
          ],
        }}
        prepare={(values) => ({
          ...values,
          scenes: chapters.find((item) => item.id === values["id"])?.scenes ?? [],
        })}
      />

      <EntityFormDialog
        open={sceneDialogOpen}
        onOpenChange={(open) => {
          setSceneDialogOpen(open);
          if (!open) setEditorScene(null);
        }}
        title={`${editorScene ? "Editar" : "Nova"} cena${selectedChapter ? ` · ${selectedChapter.title}` : ""}`}
        fields={sceneFormFields}
        initial={initialScene}
        validate={sceneFormError}
        onSubmit={saveScene}
        description={`A cena, seus diálogos, escolhas e associações serão salvos no banco do servidor. Use o ID exato da cena de destino; deixe-o vazio para seguir a ordem. A coluna “condição” é salva como anotação, mas ainda não filtra escolhas no jogo. A quinta coluna recebe UUIDs de modelos de recompensa; a sexta, UUIDs de missões publicadas e atribuídas; a sétima avança objetivos no formato ID_DA_MISSÃO:ID_DO_OBJETIVO:QUANTIDADE. ${availableRewards.length ? `Modelos de recompensa: ${availableRewards.map((reward) => `${reward.quest} (${reward.id})`).join("; ")}` : "Cadastre modelos de recompensa na área Economia antes de vinculá-los."}`}
        submitLabel="Salvar no servidor"
      />
    </section>
  );
}
