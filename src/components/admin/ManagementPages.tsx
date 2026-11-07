import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { CrudPage, DetailRow, type Column } from "@/components/common/CrudPage";
import type { FieldDef, Option } from "@/components/common/EntityForm";
import { PageHeader } from "@/components/common/ui-bits";
import { EntityProfileEditor } from "@/components/admin/EntityProfileEditor";
import { useCollection } from "@/hooks/use-collection";
import { adminContentRequest } from "@/lib/admin-content-api";
import type {
  Campaign,
  Collection,
  Character,
  DemoDB,
  DropEntry,
  Item,
  Monster,
  Npc,
  Player,
  QuestReward,
  Skill,
  Transaction,
} from "@/types/entities";
import {
  BookOpen,
  Coins,
  Gem,
  Languages,
  ScrollText,
  Shield,
  Skull,
  Sparkles,
  Swords,
  Users,
} from "lucide-react";

const enumOptions = (values: string[], labels: Record<string, string> = {}): Option[] =>
  values.map((value) => ({ value, label: labels[value] ?? value }));

type EconomySettings = {
  coins: string;
  purchaseMarkup: string;
  saleRate: string;
  rules: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function EconomySettingsCard() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["admin-content", "economy-config"],
    queryFn: () => adminContentRequest("/api/admin/content/economy/config"),
  });
  const [values, setValues] = useState<EconomySettings>({
    coins: "ouro",
    purchaseMarkup: "0",
    saleRate: "50",
    rules: "",
  });

  useEffect(() => {
    if (!isRecord(query.data)) return;
    const data = query.data;
    const rules = isRecord(data["rules"]) ? data["rules"] : {};
    setValues({
      coins: Array.isArray(data["coins"])
        ? data["coins"].filter((coin): coin is string => typeof coin === "string").join(", ")
        : "ouro",
      purchaseMarkup: String(data["purchase_markup_percent"] ?? 0),
      saleRate: String(data["sale_rate_percent"] ?? 50),
      rules: typeof rules["description"] === "string" ? rules["description"] : "",
    });
  }, [query.data]);

  const save = useMutation({
    mutationFn: () =>
      adminContentRequest("/api/admin/content/economy/config", "PUT", {
        value: {
          coins: values.coins
            .split(",")
            .map((coin) => coin.trim())
            .filter(Boolean),
          purchase_markup_percent: Number(values.purchaseMarkup),
          sale_rate_percent: Number(values.saleRate),
          rules: { description: values.rules.trim() },
        },
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-content", "economy-config"] });
      toast.success("Regras comerciais salvas no servidor.");
    },
    onError: (error) =>
      toast.error("Não foi possível salvar as regras comerciais.", {
        description: error instanceof Error ? error.message : String(error),
      }),
  });

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const markup = Number(values.purchaseMarkup);
    const saleRate = Number(values.saleRate);
    if (!values.coins.split(",").some((coin) => coin.trim())) {
      toast.error("Informe ao menos uma moeda.");
      return;
    }
    if (!Number.isFinite(markup) || markup < 0 || markup > 1000) {
      toast.error("O acréscimo de compra deve ficar entre 0 e 1000%.");
      return;
    }
    if (!Number.isFinite(saleRate) || saleRate < 0 || saleRate > 100) {
      toast.error("O valor de revenda deve ficar entre 0 e 100%.");
      return;
    }
    save.mutate();
  }

  return (
    <Card className="panel-card mb-5">
      <CardHeader>
        <CardTitle className="font-display text-xl">Regras comerciais do universo</CardTitle>
        <CardDescription>
          Configuração oficial salva no banco; não modifica moedas ou transações de personagens
          existentes.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <p className="text-sm text-muted-foreground">Carregando regras do servidor…</p>
        ) : query.error ? (
          <p role="alert" className="text-sm text-destructive">
            Não foi possível carregar as regras comerciais. {query.error.message}
          </p>
        ) : (
          <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-2 text-sm font-medium">
              Moedas (separadas por vírgula)
              <Input
                value={values.coins}
                onChange={(event) => setValues((old) => ({ ...old, coins: event.target.value }))}
              />
            </label>
            <label className="space-y-2 text-sm font-medium">
              Acréscimo nas compras (%)
              <Input
                type="number"
                min={0}
                max={1000}
                value={values.purchaseMarkup}
                onChange={(event) =>
                  setValues((old) => ({ ...old, purchaseMarkup: event.target.value }))
                }
              />
            </label>
            <label className="space-y-2 text-sm font-medium">
              Valor de revenda (% do preço)
              <Input
                type="number"
                min={0}
                max={100}
                value={values.saleRate}
                onChange={(event) => setValues((old) => ({ ...old, saleRate: event.target.value }))}
              />
            </label>
            <label className="space-y-2 text-sm font-medium sm:col-span-2">
              Regras comerciais
              <Textarea
                rows={3}
                value={values.rules}
                onChange={(event) => setValues((old) => ({ ...old, rules: event.target.value }))}
              />
            </label>
            <div className="sm:col-span-2">
              <Button type="submit" disabled={save.isPending}>
                {save.isPending ? "Salvando..." : "Salvar regras no servidor"}
              </Button>
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  );
}

const campaignStatuses = enumOptions(["planejada", "em_andamento", "pausada", "concluida"], {
  planejada: "Planejada",
  em_andamento: "Em andamento",
  pausada: "Pausada",
  concluida: "Concluída",
});
const publishStatuses = enumOptions(["rascunho", "publicado"], {
  rascunho: "Rascunho",
  publicado: "Publicado",
});
const playerStatuses = enumOptions(["ativo", "inativo", "banido"], {
  ativo: "Ativo",
  inativo: "Inativo",
  banido: "Banido",
});
const skillCategories = enumOptions(
  [
    "fisica",
    "fogo",
    "gelo",
    "luz",
    "trevas",
    "raio",
    "explosao",
    "cura",
    "buff",
    "debuff",
    "especial",
    "carreira",
    "agua",
    "vento",
    "terra",
    "yin",
    "yang",
    "suporte",
    "carreira",
  ],
  { carreira: "Carreira (registro antigo)" },
);
const skillTargets = enumOptions(["proprio", "aliado", "inimigo", "area"], {
  proprio: "Próprio",
  aliado: "Aliado",
  inimigo: "Inimigo",
  area: "Área",
});
const itemCategories = enumOptions(
  ["arma", "armadura", "acessorio", "consumivel", "material", "missao", "carreira"],
  {
    arma: "Arma",
    armadura: "Armadura",
    acessorio: "Acessório",
    consumivel: "Consumível",
    material: "Material",
    missao: "Missão",
    carreira: "Carreira (registro antigo)",
  },
);
const rarities = enumOptions(["comum", "incomum", "raro", "epico", "lendario"], {
  comum: "Comum",
  incomum: "Incomum",
  raro: "Raro",
  epico: "Épico",
  lendario: "Lendário",
});

function StatusBadge({ value }: { value: string }) {
  const label =
    [...campaignStatuses, ...publishStatuses, ...playerStatuses].find(
      (item) => item.value === value,
    )?.label ?? value;
  const tone =
    value === "em_andamento" || value === "ativo" || value === "publicado"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
      : value === "pausada" || value === "rascunho" || value === "planejada"
        ? "border-amber-500/30 bg-amber-500/10 text-amber-200"
        : "border-border bg-muted text-muted-foreground";
  return (
    <Badge variant="outline" className={tone}>
      {label}
    </Badge>
  );
}

function useEntityOptions<K extends Collection>(
  collection: K,
  label: (entity: DemoDB[K][number]) => string,
): Option[] {
  const { data = [] } = useCollection(collection);
  return useMemo(
    () => data.map((entity) => ({ value: entity.id, label: label(entity) })),
    [data, label],
  );
}

const columns = <T,>(...items: Column<T>[]) => items;
const textField = (name: string, label: string, required = false): FieldDef => ({
  name,
  label,
  type: "text",
  required,
});
const areaField = (name: string, label: string): FieldDef => ({
  name,
  label,
  type: "textarea",
  full: true,
});
const numberField = (name: string, label: string, min = 0, max?: number): FieldDef => ({
  name,
  label,
  type: "number",
  min,
  ...(max !== undefined ? { max } : {}),
});
const selectField = (name: string, label: string, options: Option[]): FieldDef => ({
  name,
  label,
  type: "select",
  options,
  required: true,
});
const listField = (name: string, label: string): FieldDef => ({
  name,
  label,
  type: "list",
  full: true,
});

export function CampaignsPage() {
  const chapterOptions = useEntityOptions(
    "chapters",
    (chapter) => `${chapter.order}. ${chapter.title}`,
  );
  const playerOptions = useEntityOptions("players", (player) => player.displayName);
  const chapterNames = useEntityOptions("chapters", (chapter) => chapter.title);
  const columns = useMemo(
    () => [
      { key: "title", label: "Campanha" },
      {
        key: "status",
        label: "Estado",
        render: (row: Campaign) => <StatusBadge value={row.status} />,
      },
      {
        key: "startChapterId",
        label: "Capítulo atual",
        render: (row: Campaign) =>
          chapterNames.find((option) => option.value === row.startChapterId)?.label ??
          "Não definido",
      },
      {
        key: "playerIds",
        label: "Jogadores",
        render: (row: Campaign) => `${row.playerIds.length} participantes`,
      },
    ],
    [chapterNames],
  );
  return (
    <CrudPage
      collection="campaigns"
      title="Campanhas"
      description="Organize as jornadas, participantes e o estado atual de cada mundo."
      icon={ScrollText}
      entityLabel="campanha"
      newEntityLabel="Nova campanha"
      columns={columns}
      readOnly
      fields={[
        textField("title", "Título", true),
        selectField("status", "Status", campaignStatuses),
        areaField("description", "Descrição"),
        selectField("startChapterId", "Capítulo atual", [
          { value: "none", label: "Não definido" },
          ...chapterOptions,
        ]),
        numberField("minPlayers", "Mínimo de jogadores", 3, 5),
        numberField("maxPlayers", "Máximo de jogadores", 3, 5),
        {
          name: "playerIds",
          label: "Jogadores participantes",
          type: "multi",
          options: playerOptions,
        },
        areaField("worldState", "Estado do mundo"),
      ]}
      defaults={() => ({
        title: "",
        description: "",
        status: "planejada",
        minPlayers: 3,
        maxPlayers: 5,
        startChapterId: chapterOptions[0]?.value ?? "none",
        playerIds: [],
        worldState: "",
      })}
      searchKeys={["title", "description", "worldState"]}
      filter={{ key: "status", label: "Status", options: campaignStatuses }}
      prepare={(values) => ({
        ...values,
        startChapterId: values["startChapterId"] === "none" ? "" : values["startChapterId"],
      })}
      validate={(values) => {
        const minimum = Number(values["minPlayers"]);
        const maximum = Number(values["maxPlayers"]);
        if (minimum < 3 || maximum > 5)
          return "A configuração de jogadores deve ficar entre 3 e 5.";
        if (minimum > maximum) return "O mínimo de jogadores não pode superar o máximo.";
        if ((values["playerIds"] as string[]).length > maximum)
          return "A quantidade de participantes supera o máximo da campanha.";
        return null;
      }}
    />
  );
}

export function PlayersAndCharactersPage({
  initialTab = "players",
}: {
  initialTab?: "players" | "characters" | "npcs";
}) {
  const [activeTab, setActiveTab] = useState(initialTab);
  const campaigns = useEntityOptions("campaigns", (campaign) => campaign.title);
  const players = useEntityOptions("players", (player) => player.displayName);
  const items = useEntityOptions("items", (item) => item.name);
  const skills = useEntityOptions("skills", (skill) => skill.name);
  const { data: allCharacters = [] } = useCollection("characters");
  const playerNames = useEntityOptions("players", (player) => player.displayName);
  const campaignOptions = campaigns;
  const playersColumns = useMemo(
    () => [
      { key: "displayName", label: "Jogador" },
      { key: "discordId", label: "ID do Discord" },
      {
        key: "campaignId",
        label: "Campanha",
        render: (row: Player) =>
          campaigns.find((option) => option.value === row.campaignId)?.label ?? "Sem campanha",
      },
      {
        key: "status",
        label: "Status",
        render: (row: Player) => <StatusBadge value={row.status} />,
      },
      {
        key: "id",
        label: "Personagens",
        render: (row: Player) =>
          `${allCharacters.filter((character) => character.playerId === row.id).length} vinculado(s)`,
      },
    ],
    [allCharacters, campaigns],
  );
  const characterColumns = useMemo(
    () => [
      { key: "name", label: "Personagem" },
      {
        key: "playerId",
        label: "Jogador",
        render: (row: Character) =>
          playerNames.find((option) => option.value === row.playerId)?.label ?? "Sem vínculo",
      },
      { key: "combatClass", label: "Classe" },
      { key: "level", label: "Nível" },
      { key: "xp", label: "XP" },
      { key: "hp", label: "HP", render: (row: Character) => `${row.hp} / ${row.hpMax}` },
      { key: "mana", label: "Mana", render: (row: Character) => `${row.mana} / ${row.manaMax}` },
      { key: "gold", label: "Moedas", render: (row: Character) => `${row.gold} ouro` },
    ],
    [playerNames],
  );
  const npcColumns = columns<Npc>(
    { key: "name", label: "NPC" },
    { key: "role", label: "Papel" },
    {
      key: "campaignId",
      label: "Campanha",
      render: (row) =>
        campaigns.find((option) => option.value === row["campaignId"])?.label ?? "Sem campanha",
    },
    {
      key: "playerRelations",
      label: "Relações",
      render: (row) => `${row.playerRelations?.length ?? 0} vínculo(s)`,
    },
    {
      key: "placeholder",
      label: "Origem",
      render: (row) => (row.placeholder ? <Badge variant="outline">Provisório</Badge> : "Original"),
    },
  );
  const characterFields: FieldDef[] = [
    textField("name", "Nome", true),
    selectField("playerId", "Jogador", [{ value: "none", label: "Sem vínculo" }, ...players]),
    textField("combatClass", "Classe"),
    numberField("level", "Nível", 1),
    numberField("xp", "Experiência"),
    numberField("hp", "HP atual"),
    numberField("hpMax", "HP máximo", 1),
    numberField("mana", "Mana atual"),
    numberField("manaMax", "Mana máxima"),
    numberField("gold", "Moedas"),
    numberField("attributes.forca", "Força"),
    numberField("attributes.agilidade", "Agilidade"),
    numberField("attributes.intelecto", "Intelecto"),
    numberField("attributes.vitalidade", "Vitalidade"),
    numberField("attributes.espirito", "Espírito"),
    { name: "equipmentIds", label: "Equipamentos", type: "multi", options: items },
    { name: "skillIds", label: "Habilidades", type: "multi", options: skills },
    {
      name: "inventoryInput",
      label: "Inventário (um ID de item e quantidade por linha, separados por vírgula)",
      type: "list",
      full: true,
      placeholder: "itm_004, 2",
    },
    areaField("history", "História"),
  ];
  return (
    <section>
      <PageHeader
        title="Jogadores e personagens"
        description="Gerencie participantes, vínculos e fichas da mesa."
        icon={Users}
      />
      <Tabs
        value={activeTab}
        onValueChange={(value) => {
          if (value === "players" || value === "characters" || value === "npcs")
            setActiveTab(value);
        }}
      >
        <TabsList className="mb-5 flex h-auto w-full justify-start overflow-x-auto">
          <TabsTrigger value="players">Jogadores</TabsTrigger>
          <TabsTrigger value="characters">Personagens</TabsTrigger>
          <TabsTrigger value="npcs">NPCs</TabsTrigger>
        </TabsList>
        <TabsContent value="players">
          <CrudPage
            collection="players"
            title="Jogadores"
            description="Cadastro de participantes e sua campanha atual."
            icon={Users}
            entityLabel="jogador"
            columns={playersColumns}
            readOnly
            fields={[
              textField("displayName", "Nome", true),
              textField("discordId", "ID do Discord"),
              selectField("campaignId", "Campanha", [
                { value: "none", label: "Sem campanha" },
                ...campaigns,
              ]),
              selectField("status", "Status", playerStatuses),
              textField("registeredAt", "Data de cadastro"),
            ]}
            defaults={() => ({
              displayName: "",
              discordId: "",
              campaignId: campaigns[0]?.value ?? "none",
              status: "ativo",
              registeredAt: new Date().toISOString().slice(0, 10),
            })}
            searchKeys={["displayName", "discordId"]}
            filter={{ key: "status", label: "Status", options: playerStatuses }}
            formValues={(player) => ({ campaignId: player.campaignId || "none" })}
            prepare={(values) => ({
              ...values,
              campaignId: values["campaignId"] === "none" ? "" : values["campaignId"],
            })}
          />
        </TabsContent>
        <TabsContent value="characters">
          <CrudPage
            collection="characters"
            title="Personagens"
            description="Fichas, atributos, recursos e equipamentos."
            icon={Shield}
            entityLabel="personagem"
            columns={characterColumns}
            readOnly
            fields={characterFields}
            defaults={() => ({
              name: "",
              playerId: players[0]?.value ?? "none",
              combatClass: "",
              level: 1,
              xp: 0,
              hp: 10,
              hpMax: 10,
              mana: 0,
              manaMax: 0,
              gold: 0,
              attributes: { forca: 1, agilidade: 1, intelecto: 1, vitalidade: 1, espirito: 1 },
              "attributes.forca": 1,
              "attributes.agilidade": 1,
              "attributes.intelecto": 1,
              "attributes.vitalidade": 1,
              "attributes.espirito": 1,
              equipmentIds: [],
              skillIds: [],
              inventory: [],
              inventoryInput: [],
              history: "",
            })}
            searchKeys={["name", "combatClass"]}
            formValues={(character) => ({
              playerId: character.playerId || "none",
              "attributes.forca": character.attributes.forca,
              "attributes.agilidade": character.attributes.agilidade,
              "attributes.intelecto": character.attributes.intelecto,
              "attributes.vitalidade": character.attributes.vitalidade,
              "attributes.espirito": character.attributes.espirito,
              inventoryInput: character.inventory.map(({ itemId, qty }) => `${itemId}, ${qty}`),
            })}
            validate={(values) => {
              const invalidInventory = (values["inventoryInput"] as string[]).some((line) => {
                const [itemId, quantity] = line.split(",").map((part) => part.trim());
                return (
                  !items.some((item) => item.value === itemId) ||
                  !Number.isInteger(Number(quantity)) ||
                  Number(quantity) < 1
                );
              });
              if (invalidInventory)
                return "Confira o inventário: use um ID de item válido e uma quantidade inteira maior que zero por linha.";
              if (Number(values["hp"]) > Number(values["hpMax"]))
                return "O HP atual não pode superar o HP máximo.";
              if (Number(values["mana"]) > Number(values["manaMax"]))
                return "A mana atual não pode superar a mana máxima.";
              return null;
            }}
            prepare={(values) => {
              const {
                inventoryInput = [],
                "attributes.forca": strength,
                "attributes.agilidade": agility,
                "attributes.intelecto": intellect,
                "attributes.vitalidade": vitality,
                "attributes.espirito": spirit,
                ...entity
              } = values;
              const inventory = (inventoryInput as string[]).flatMap((line) => {
                const [itemId, quantity] = line.split(",").map((part) => part.trim());
                const qty = Number(quantity);
                return itemId && Number.isInteger(qty) && qty > 0 ? [{ itemId, qty }] : [];
              });
              return {
                ...entity,
                playerId: entity["playerId"] === "none" ? "" : entity["playerId"],
                attributes: {
                  forca: Number(strength),
                  agilidade: Number(agility),
                  intelecto: Number(intellect),
                  vitalidade: Number(vitality),
                  espirito: Number(spirit),
                },
                inventory,
              };
            }}
            renderDetail={(character) => (
              <div className="space-y-1">
                <DetailRow label="História">{character.history}</DetailRow>
                <DetailRow label="Atributos">
                  {Object.entries(character.attributes)
                    .map(([name, value]) => `${name}: ${value}`)
                    .join(" · ")}
                </DetailRow>
                <DetailRow label="Inventário">
                  {character.inventory
                    .map(
                      ({ itemId, qty }) =>
                        `${items.find((option) => option.value === itemId)?.label ?? itemId} ×${qty}`,
                    )
                    .join(" · ")}
                </DetailRow>
                <DetailRow label="Equipamentos">
                  {character.equipmentIds
                    .map((id) => items.find((option) => option.value === id)?.label ?? id)
                    .join(", ")}
                </DetailRow>
              </div>
            )}
          />
        </TabsContent>
        <TabsContent value="npcs">
          <CrudPage
            collection="npcs"
            title="NPCs"
            description="Personagens do mundo, diálogos e missões."
            allowDuplicate
            icon={Languages}
            entityLabel="NPC"
            columns={npcColumns}
            fields={[
              textField("name", "Nome", true),
              areaField("description", "Descrição"),
              textField("personality", "Personalidade"),
              textField("role", "Papel na história"),
              selectField("campaignId", "Campanha", [
                { value: "none", label: "Sem campanha" },
                ...campaignOptions,
              ]),
              textField("campaignRelation", "Relação com a campanha"),
              textField("imageUrl", "Imagem (URL PNG)"),
              selectField("status", "Publicação", [
                { value: "rascunho", label: "Rascunho" },
                { value: "publicado", label: "Publicado" },
                { value: "inactive", label: "Inativo" },
              ]),
              { name: "isActive", label: "NPC ativo", type: "checkbox" },
              listField(
                "playerRelationsInput",
                "Relações com jogadores (um por linha: ID do jogador, relação)",
              ),
              listField("dialogues", "Diálogos"),
              listField("quests", "Missões"),
              areaField("relationshipConditions", "Condições de relacionamento"),
              selectField(
                "placeholder",
                "Origem do registro",
                enumOptions(["false", "true"], { false: "Original", true: "Conteúdo provisório" }),
              ),
            ]}
            defaults={() => ({
              name: "",
              description: "",
              personality: "",
              role: "",
              campaignId: campaignOptions[0]?.value ?? "none",
              campaignRelation: "",
              imageUrl: "",
              status: "rascunho",
              isActive: true,
              playerRelations: [],
              playerRelationsInput: [],
              dialogues: [],
              quests: [],
              relationshipConditions: "",
              placeholder: false,
            })}
            searchKeys={["name", "description", "role"]}
            formValues={(npc) => ({
              placeholder: String(npc.placeholder),
              campaignId: npc.campaignId || "none",
              playerRelationsInput:
                npc.playerRelations?.map(
                  ({ playerId, relationship }) => `${playerId}, ${relationship}`,
                ) ?? [],
            })}
            validate={(values) => {
              const invalidRelation = (values["playerRelationsInput"] as string[]).some((line) => {
                const [playerId, relationship] = line.split(",").map((part) => part.trim());
                return !players.some((player) => player.value === playerId) || !relationship;
              });
              return invalidRelation
                ? "Cada relação deve usar um ID de jogador válido e uma descrição separados por vírgula."
                : null;
            }}
            prepare={(values) => {
              const { playerRelationsInput = [], ...entity } = values;
              return {
                ...entity,
                placeholder: entity["placeholder"] === "true",
                campaignId: entity["campaignId"] === "none" ? "" : entity["campaignId"],
                playerRelations: (playerRelationsInput as string[]).map((line) => {
                  const [playerId = "", ...parts] = line.split(",").map((part) => part.trim());
                  return { playerId, relationship: parts.join(", ") };
                }),
              };
            }}
            filter={{
              key: "status",
              label: "Publicação",
              options: enumOptions(["rascunho", "publicado", "inactive"], {
                rascunho: "Rascunho",
                publicado: "Publicado",
                inactive: "Inativo",
              }),
            }}
            renderDetail={(npc) => (
              <div className="space-y-1">
                <DetailRow label="Descrição">{npc.description}</DetailRow>
                <DetailRow label="Personalidade">{npc.personality}</DetailRow>
                <DetailRow label="Papel">{npc.role}</DetailRow>
                <DetailRow label="Relação com a campanha">{npc.campaignRelation}</DetailRow>
                <DetailRow label="Diálogos">{npc.dialogues.join(" · ")}</DetailRow>
                <DetailRow label="Missões">{npc.quests.join(", ")}</DetailRow>
              </div>
            )}
          />
        </TabsContent>
      </Tabs>
      {activeTab === "characters" && <EntityProfileEditor entityType="character" />}
      {activeTab === "npcs" && <EntityProfileEditor entityType="npc" />}
    </section>
  );
}

export function MonstersPage() {
  const creatureColumns = columns<Monster>(
    { key: "name", label: "Criatura" },
    { key: "level", label: "Nível" },
    { key: "hp", label: "HP" },
    { key: "attack", label: "Ataque" },
    { key: "defense", label: "Defesa" },
    { key: "xpReward", label: "XP" },
    { key: "difficulty", label: "Dificuldade" },
    {
      key: "appearanceChance",
      label: "Aparição",
      render: (row) => `${row.appearanceChance ?? 100}%`,
    },
    {
      key: "placeholder",
      label: "Origem",
      render: (row) => (row.placeholder ? <Badge variant="outline">Provisório</Badge> : "Original"),
    },
  );
  return (
    <>
      <CrudPage
        collection="monsters"
        title="Criaturas e monstros"
        description="Bestiário, atributos e recompensas de combate."
        allowDuplicate
        icon={Skull}
        entityLabel="criatura"
        newEntityLabel="Nova criatura"
        columns={creatureColumns}
        fields={[
          textField("name", "Nome", true),
          areaField("description", "Descrição"),
          numberField("level", "Nível", 1),
          numberField("hp", "HP", 1),
          numberField("attack", "Ataque"),
          numberField("defense", "Defesa"),
          numberField("speed", "Velocidade"),
          numberField("xpReward", "XP concedido"),
          selectField(
            "difficulty",
            "Dificuldade base",
            enumOptions(["easy", "medium", "difficult", "impossible", "normal", "hard", "boss"], {
              easy: "Fácil",
              medium: "Médio",
              difficult: "Difícil",
              impossible: "Impossível",
              normal: "Normal (legado)",
              hard: "Difícil (legado)",
              boss: "Boss (legado)",
            }),
          ),
          numberField("appearanceChance", "Chance de aparição (%)", 0, 100),
          textField("imageUrl", "URL de imagem PNG"),
          { name: "imageFile", label: "Enviar PNG (máx. 5 MB)", type: "image", full: true },
          { name: "isActive", label: "Monstro ativo", type: "checkbox" },
          listField("abilities", "Habilidades"),
          listField("resistances", "Resistências"),
          listField("weaknesses", "Fraquezas"),
          listField("rewards", "Recompensas"),
          selectField(
            "placeholder",
            "Origem do registro",
            enumOptions(["false", "true"], { false: "Original", true: "Conteúdo provisório" }),
          ),
        ]}
        defaults={() => ({
          name: "",
          description: "",
          level: 1,
          hp: 1,
          attack: 1,
          defense: 0,
          speed: 1,
          xpReward: 0,
          difficulty: "normal",
          appearanceChance: 100,
          isActive: true,
          abilities: [],
          resistances: [],
          weaknesses: [],
          rewards: [],
          imageUrl: "",
          placeholder: false,
        })}
        searchKeys={["name", "description"]}
        formValues={(monster) => ({ placeholder: String(monster.placeholder) })}
        prepare={(values) => ({ ...values, placeholder: values["placeholder"] === "true" })}
        filter={{
          key: "difficulty",
          label: "Dificuldade",
          options: enumOptions(["easy", "normal", "hard", "boss"]),
        }}
        renderDetail={(monster) => (
          <div className="space-y-1">
            <DetailRow label="Descrição">{monster.description}</DetailRow>
            <DetailRow label="Ataque / defesa">
              {monster.attack} / {monster.defense}
            </DetailRow>
            <DetailRow label="Velocidade">{monster.speed}</DetailRow>
            <DetailRow label="Habilidades">{monster.abilities.join(", ")}</DetailRow>
            <DetailRow label="Resistências">{monster.resistances.join(", ")}</DetailRow>
            <DetailRow label="Fraquezas">{monster.weaknesses.join(", ")}</DetailRow>
            <DetailRow label="Recompensas">{monster.rewards.join(", ")}</DetailRow>
          </div>
        )}
      />
      <EntityProfileEditor entityType="enemy" />
      <DropRulesPage />
    </>
  );
}

export function SkillsPage() {
  const skillColumns = columns<Skill>(
    { key: "name", label: "Habilidade" },
    { key: "category", label: "Tipo" },
    {
      key: "isCareer",
      label: "Subclasse",
      render: (row) => (row.isCareer ? <Badge variant="outline">Carreira</Badge> : "—"),
    },
    {
      key: "power",
      label: "Poder",
      render: (row) => (row.powerType === "nenhum" ? "Efeito" : `${row.power} ${row.powerType}`),
    },
    { key: "manaCost", label: "Mana" },
    { key: "levelReq", label: "Nível" },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
  );
  return (
    <>
      <CrudPage
        collection="skills"
        title="Magias e habilidades"
        description="Catálogo de poderes, custos, efeitos e requisitos."
        allowDuplicate
        icon={Sparkles}
        entityLabel="habilidade"
        newEntityLabel="Nova habilidade"
        columns={skillColumns}
        fields={[
          textField("name", "Nome", true),
          selectField("category", "Tipo de habilidade", skillCategories),
          {
            name: "isCareer",
            label: "Subclasse",
            type: "checkbox",
            checkboxLabel: "Esta habilidade pertence a uma carreira",
          },
          areaField("description", "Descrição"),
          numberField("manaCost", "Custo de mana"),
          numberField("power", "Dano ou cura"),
          selectField(
            "powerType",
            "Tipo de poder",
            enumOptions(["dano", "cura", "nenhum"], {
              dano: "Dano",
              cura: "Cura",
              nenhum: "Sem dano/cura",
            }),
          ),
          areaField("effects", "Efeitos"),
          selectField("target", "Alvo", skillTargets),
          numberField("levelReq", "Nível necessário"),
          numberField("cooldown", "Recarga (turnos)"),
          selectField("status", "Status", publishStatuses),
        ]}
        defaults={() => ({
          name: "",
          category: "suporte",
          isCareer: false,
          description: "",
          manaCost: 0,
          power: 0,
          powerType: "nenhum",
          effects: "",
          target: "inimigo",
          levelReq: 1,
          cooldown: 0,
          status: "rascunho",
        })}
        searchKeys={["name", "description", "effects"]}
        filter={{ key: "category", label: "Categoria", options: skillCategories }}
        renderDetail={(skill) => (
          <div className="space-y-1">
            <DetailRow label="Descrição">{skill.description}</DetailRow>
            <DetailRow label="Categoria">{skill.category}</DetailRow>
            <DetailRow label="Alvo">{skill.target}</DetailRow>
            <DetailRow label="Efeitos">{skill.effects}</DetailRow>
            <DetailRow label="Custo de mana">{skill.manaCost}</DetailRow>
            <DetailRow label="Poder">
              {skill.powerType === "nenhum" ? "Efeito" : `${skill.power} ${skill.powerType}`}
            </DetailRow>
            <DetailRow label="Recarga">{skill.cooldown} turno(s)</DetailRow>
          </div>
        )}
      />
      <EntityProfileEditor entityType="skill" />
    </>
  );
}

export function ItemsPage() {
  const itemColumns = columns<Item>(
    { key: "name", label: "Item" },
    { key: "category", label: "Tipo" },
    {
      key: "isCareer",
      label: "Subclasse",
      render: (row) => (row.isCareer ? <Badge variant="outline">Carreira</Badge> : "—"),
    },
    {
      key: "rarity",
      label: "Raridade",
      render: (row) => rarities.find((option) => option.value === row.rarity)?.label ?? row.rarity,
    },
    { key: "price", label: "Preço", render: (row) => `${row.price.toLocaleString("pt-BR")} ouro` },
    { key: "stock", label: "Estoque" },
  );
  return (
    <>
      <CrudPage
        collection="items"
        title="Itens e equipamentos"
        description="Armas, armaduras, consumíveis e tesouros."
        allowDuplicate
        icon={Gem}
        entityLabel="item"
        columns={itemColumns}
        fields={[
          textField("name", "Nome", true),
          selectField("category", "Tipo de item", itemCategories),
          {
            name: "isCareer",
            label: "Subclasse",
            type: "checkbox",
            checkboxLabel: "Este item pertence a uma carreira",
          },
          selectField("rarity", "Raridade", rarities),
          areaField("description", "Descrição"),
          numberField("price", "Preço"),
          numberField("weight", "Peso"),
          numberField("levelReq", "Nível necessário"),
          numberField("stock", "Estoque"),
          textField("bonuses", "Bônus"),
          areaField("effects", "Efeitos"),
          textField("imageUrl", "Imagem (URL)"),
          textField("usage", "Instruções de utilização"),
          { name: "isActive", label: "Item ativo", type: "checkbox" },
        ]}
        defaults={() => ({
          name: "",
          category: "arma",
          isCareer: false,
          rarity: "comum",
          description: "",
          price: 0,
          weight: 0,
          bonuses: "",
          effects: "",
          levelReq: 0,
          stock: 0,
          imageUrl: "",
          usage: "",
          isActive: true,
        })}
        searchKeys={["name", "description", "bonuses", "effects"]}
        filter={{ key: "category", label: "Categoria", options: itemCategories }}
        renderDetail={(item) => (
          <div className="space-y-1">
            <DetailRow label="Descrição">{item.description}</DetailRow>
            <DetailRow label="Categoria / raridade">
              {item.category} / {item.rarity}
            </DetailRow>
            <DetailRow label="Bônus">{item.bonuses}</DetailRow>
            <DetailRow label="Efeitos">{item.effects}</DetailRow>
            <DetailRow label="Preço / peso">
              {item.price} moedas / {item.weight}
            </DetailRow>
            <DetailRow label="Uso">{item.usage}</DetailRow>
          </div>
        )}
      />
      <EntityProfileEditor entityType="item" />
    </>
  );
}

export function DropRulesPage() {
  const monsters = useEntityOptions("monsters", (monster) => monster.name);
  const items = useEntityOptions("items", (item) => item.name);
  const dropColumns = useMemo(
    () => [
      {
        key: "monsterId",
        label: "Criatura",
        render: (row: DropEntry) =>
          monsters.find((option) => option.value === row.monsterId)?.label ?? "Não definida",
      },
      {
        key: "itemId",
        label: "Item",
        render: (row: DropEntry) =>
          items.find((option) => option.value === row.itemId)?.label ?? "Não definido",
      },
      { key: "chance", label: "Chance", render: (row: DropEntry) => `${row.chance}%` },
    ],
    [items, monsters],
  );
  return (
    <CrudPage
      collection="drops"
      title="Recompensas e drops"
      description="Defina quais itens cada inimigo, miniboss ou boss pode deixar, a chance e a quantidade."
      icon={Swords}
      entityLabel="drop"
      columns={dropColumns}
      fields={[
        selectField("monsterId", "Inimigo, miniboss ou boss", monsters),
        selectField("itemId", "Item da recompensa", items),
        numberField("chance", "Chance (%)", 0, 100),
        numberField("minQuantity", "Quantidade mínima", 1),
        numberField("maxQuantity", "Quantidade máxima", 1),
      ]}
      defaults={() => ({
        monsterId: monsters[0]?.value ?? "",
        itemId: items[0]?.value ?? "",
        chance: 50,
        minQuantity: 1,
        maxQuantity: 1,
      })}
      searchKeys={["monsterId", "itemId"]}
      validate={(values) => {
        if (Number(values["chance"]) > 100) return "A chance máxima é 100%.";
        if (Number(values["maxQuantity"]) < Number(values["minQuantity"]))
          return "A quantidade máxima não pode ser menor que a mínima.";
        return null;
      }}
    />
  );
}

export function EconomyPage() {
  const characters = useEntityOptions("characters", (character) => character.name);
  const items = useEntityOptions("items", (item) => item.name);
  const transactionColumns = useMemo(
    () => [
      { key: "date", label: "Data" },
      {
        key: "characterId",
        label: "Personagem",
        render: (row: Transaction) =>
          characters.find((option) => option.value === row.characterId)?.label ?? "Não vinculado",
      },
      { key: "kind", label: "Tipo" },
      { key: "description", label: "Descrição" },
      {
        key: "amount",
        label: "Valor",
        render: (row: Transaction) =>
          `${row.amount > 0 ? "+" : ""}${row.amount.toLocaleString("pt-BR")} ouro`,
      },
    ],
    [characters],
  );
  const rewardColumns = columns<QuestReward>(
    { key: "quest", label: "Missão" },
    { key: "gold", label: "Ouro" },
    { key: "xp", label: "XP" },
    { key: "itemIds", label: "Itens", render: (row) => `${row.itemIds.length} recompensa(s)` },
  );
  return (
    <section>
      <PageHeader
        title="Economia e recompensas"
        description="Acompanhe saldos, transações, missões e tabelas de drop."
        icon={Coins}
      />
      <EconomySettingsCard />
      <Tabs defaultValue="transactions">
        <TabsList className="mb-5 flex h-auto w-full justify-start overflow-x-auto">
          <TabsTrigger value="transactions">Transações</TabsTrigger>
          <TabsTrigger value="rewards">Recompensas de missões</TabsTrigger>
          <TabsTrigger value="drops">Tabela de drop</TabsTrigger>
        </TabsList>
        <TabsContent value="transactions">
          <CrudPage
            collection="transactions"
            title="Histórico de transações"
            description="Movimentações registradas para os personagens."
            icon={Coins}
            entityLabel="transação"
            newEntityLabel="Nova transação"
            columns={transactionColumns}
            fields={[
              selectField("characterId", "Personagem", characters),
              selectField("kind", "Tipo", enumOptions(["compra", "venda", "recompensa", "drop"])),
              textField("description", "Descrição", true),
              numberField("amount", "Valor positivo", 1),
            ]}
            appendOnly
            readOnly={!characters.length}
            headerExtra={
              !characters.length ? (
                <p className="mb-3 rounded-lg border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
                  Não há personagens salvos no banco para vincular uma transação. As contas e fichas
                  são consultadas da API.
                </p>
              ) : undefined
            }
            defaults={() => ({
              characterId: characters[0]?.value ?? "",
              kind: "recompensa",
              description: "",
              amount: 1,
            })}
            searchKeys={["description", "date"]}
            filter={{
              key: "kind",
              label: "Tipo",
              options: enumOptions(["compra", "venda", "recompensa", "drop"]),
            }}
            formValues={(transaction) => ({ characterId: transaction.characterId })}
          />
        </TabsContent>
        <TabsContent value="rewards">
          <CrudPage
            collection="questRewards"
            title="Recompensas de missões"
            description="Defina ouro, experiência e itens por objetivo."
            icon={BookOpen}
            entityLabel="recompensa"
            newEntityLabel="Nova recompensa"
            columns={rewardColumns}
            fields={[
              textField("quest", "Missão", true),
              areaField("description", "Descrição"),
              numberField("gold", "Ouro"),
              numberField("xp", "XP"),
              { name: "itemIds", label: "Itens da recompensa", type: "multi", options: items },
            ]}
            defaults={() => ({ quest: "", gold: 0, xp: 0, itemIds: [] })}
            searchKeys={["quest"]}
          />
        </TabsContent>
        <TabsContent value="drops">
          <DropRulesPage />
        </TabsContent>
      </Tabs>
    </section>
  );
}

export type ManagedPageId =
  "campaigns" | "story" | "players" | "characters" | "creatures" | "skills" | "items" | "economy";
