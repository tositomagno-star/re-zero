import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  Backpack,
  BookOpen,
  CheckCircle2,
  Coins,
  Heart,
  LogOut,
  Play,
  Sparkles,
  Zap,
} from "lucide-react";

import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs";
import {
  getCampaignCharacterSheet,
  getCampaignQuests,
  acceptCampaignQuest,
  equipCampaignCharacterItem,
  unequipCampaignCharacterItem,
  type CampaignQuest,
  updateCampaignCharacter,
  type CharacterSheet,
} from "../../lib/auth-api";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Não foi possível carregar a ficha.";
}

const categorySlots: Record<string, string[]> = {
  helmet: ["head"],
  crown: ["head"],
  capacete: ["head"],
  armor: ["body"],
  clothing: ["body"],
  armadura: ["body"],
  gloves: ["hands"],
  luvas: ["hands"],
  weapon: ["main_hand", "off_hand"],
  sword: ["main_hand", "off_hand"],
  espada: ["main_hand", "off_hand"],
  staff: ["main_hand"],
  cajado: ["main_hand"],
  shield: ["off_hand"],
  escudo: ["off_hand"],
  boots: ["feet"],
  botas: ["feet"],
  ring: ["accessory_1", "accessory_2"],
  anel: ["accessory_1", "accessory_2"],
  necklace: ["neck"],
  amulet: ["neck"],
  colar: ["neck"],
};

function slotsForCategory(category: string): string[] {
  const normalized = category.trim().toLowerCase();
  return categorySlots[normalized] ?? [];
}

const slotLabels: Record<string, string> = {
  head: "Cabeça",
  body: "Corpo",
  hands: "Mãos",
  main_hand: "Arma principal",
  off_hand: "Arma secundária",
  feet: "Pés",
  accessory_1: "Acessório 1",
  accessory_2: "Acessório 2",
  neck: "Pescoço",
};

function EmptyState({ children }: { children: string }) {
  return (
    <p className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
      {children}
    </p>
  );
}

function ResourceBar({
  label,
  current,
  maximum,
  icon: Icon,
  color,
}: {
  label: string;
  current: number;
  maximum: number;
  icon: typeof Heart;
  color: string;
}) {
  const percentage = maximum > 0 ? Math.min((current / maximum) * 100, 100) : 0;
  return (
    <div className="rounded-xl border border-border/80 bg-background/50 p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
          <Icon className={`size-4 ${color}`} />
          {label}
        </span>
        <span className="font-semibold tabular-nums text-foreground">
          {current} / {maximum}
        </span>
      </div>
      <div
        className="mt-3 h-2 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={maximum}
        aria-valuenow={current}
      >
        <div
          className={`h-full rounded-full ${color.replace("text-", "bg-")}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

export function CharacterSheet({
  campaignId,
  onBack,
  onCharacterRenamed,
  onLogout,
}: {
  campaignId: string;
  onBack: () => void;
  onCharacterRenamed: (name: string) => void;
  onLogout: () => Promise<void>;
}) {
  const [sheet, setSheet] = useState<CharacterSheet | null>(null);
  const [campaignQuests, setCampaignQuests] = useState<CampaignQuest[]>([]);
  const [acceptingQuestId, setAcceptingQuestId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(true);
  const [savingName, setSavingName] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [reload, setReload] = useState(0);
  const [equipmentBusyId, setEquipmentBusyId] = useState<string | null>(null);
  const [inventoryCategory, setInventoryCategory] = useState("all");

  async function equipItem(itemId: string, slot: string) {
    setEquipmentBusyId(itemId);
    setError("");
    setFeedback("");
    try {
      await equipCampaignCharacterItem(campaignId, itemId, slot);
      setFeedback("Equipamento atualizado.");
      setReload((current) => current + 1);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setEquipmentBusyId(null);
    }
  }

  async function unequipItem(itemId: string) {
    setEquipmentBusyId(itemId);
    setError("");
    setFeedback("");
    try {
      await unequipCampaignCharacterItem(campaignId, itemId);
      setFeedback("Equipamento removido.");
      setReload((current) => current + 1);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setEquipmentBusyId(null);
    }
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setSheet(null);
    void Promise.all([getCampaignCharacterSheet(campaignId), getCampaignQuests(campaignId)])
      .then(([result, quests]) => {
        if (!active) return;
        setSheet(result);
        setCampaignQuests(quests);
        setName(result.name);
      })
      .catch((requestError: unknown) => {
        if (active) setError(errorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [campaignId, reload]);

  async function saveName(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSavingName(true);
    setError("");
    setFeedback("");
    try {
      await updateCampaignCharacter(campaignId, name);
      const updatedName = name.trim();
      setName(updatedName);
      setSheet((current) => (current === null ? current : { ...current, name: updatedName }));
      onCharacterRenamed(updatedName);
      setFeedback("Nome do personagem salvo.");
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSavingName(false);
    }
  }

  async function acceptQuest(questId: string) {
    setAcceptingQuestId(questId);
    setError("");
    try {
      await acceptCampaignQuest(campaignId, questId);
      setReload((value) => value + 1);
      setFeedback("Missão iniciada. O progresso será atualizado pelos eventos da aventura.");
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setAcceptingQuestId(null);
    }
  }

  return (
    <main className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-border/70 bg-background/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-5 py-4 sm:px-8">
          <Button type="button" variant="ghost" size="sm" onClick={onBack}>
            <ArrowLeft className="size-4" />
            Voltar ao lobby
          </Button>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-muted-foreground sm:inline">
              Ficha do personagem
            </span>
            <Button type="button" variant="ghost" size="sm" onClick={() => void onLogout()}>
              <LogOut className="size-4" />
              Sair
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-5 py-8 sm:px-8 sm:py-12">
        {loading && (
          <p role="status" className="py-16 text-center text-sm text-muted-foreground">
            Carregando ficha...
          </p>
        )}
        {error && (
          <div
            role="alert"
            className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
          >
            <span>{error}</span>
            {sheet === null && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setReload((value) => value + 1)}
              >
                Tentar novamente
              </Button>
            )}
          </div>
        )}
        {feedback && (
          <p
            role="status"
            aria-live="polite"
            className="mb-6 rounded-lg border border-emerald-500/25 bg-emerald-500/5 p-3 text-sm text-emerald-300"
          >
            {feedback}
          </p>
        )}
        {!loading && sheet && (
          <>
            <div className="mb-6">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
                Crônicas do Reino
              </p>
              <h1 className="mt-2 break-all font-serif text-3xl font-semibold text-foreground sm:text-4xl">
                {sheet.name}
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                {sheet.character_class || "Classe não definida"}
                {sheet.ancestry ? ` · ${sheet.ancestry}` : ""}
                {" · "}Nível {sheet.level}
              </p>
            </div>

            <Tabs defaultValue="overview">
              <TabsList className="mb-6 h-auto w-full justify-start overflow-x-auto">
                <TabsTrigger value="overview">Visão geral</TabsTrigger>
                <TabsTrigger value="attributes">Atributos e recursos</TabsTrigger>
                <TabsTrigger value="inventory">Inventário e equipamentos</TabsTrigger>
                <TabsTrigger value="skills">Habilidades</TabsTrigger>
                <TabsTrigger value="quests">Missões</TabsTrigger>
              </TabsList>

              <TabsContent value="overview" className="space-y-5">
                <section className="fantasy-card rounded-2xl border p-5 sm:p-7">
                  <h2 className="font-serif text-xl font-semibold text-foreground">Personagem</h2>
                  {sheet.description ? (
                    <p className="mt-3 whitespace-pre-wrap leading-7 text-muted-foreground">
                      {sheet.description}
                    </p>
                  ) : (
                    <p className="mt-3 text-sm text-muted-foreground">
                      Ainda não há uma descrição registrada.
                    </p>
                  )}
                  <div className="mt-5 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-lg border border-border/80 bg-background/50 p-4">
                      <p className="text-xs text-muted-foreground">Nível</p>
                      <p className="mt-1 text-xl font-semibold">{sheet.level}</p>
                      <p className="text-xs text-muted-foreground">
                        {sheet.xp_to_next_level === null
                          ? `${sheet.xp} XP · nível máximo`
                          : `${sheet.xp} / ${sheet.xp_to_next_level} XP nesta faixa`}
                      </p>
                      {sheet.xp_to_next_level !== null && (
                        <div
                          className="mt-3 h-2 overflow-hidden rounded-full bg-muted"
                          role="progressbar"
                          aria-label="Progresso de experiência para o próximo nível"
                          aria-valuemin={0}
                          aria-valuemax={sheet.xp_to_next_level}
                          aria-valuenow={Math.min(sheet.xp, sheet.xp_to_next_level)}
                        >
                          <div
                            className="h-full rounded-full bg-primary transition-[width]"
                            style={{ width: `${sheet.xp_progress_percent}%` }}
                          />
                        </div>
                      )}
                      <p className="mt-2 text-xs text-muted-foreground">
                        {sheet.attribute_points} pontos de atributo disponíveis
                      </p>
                    </div>
                    <div className="rounded-lg border border-border/80 bg-background/50 p-4">
                      <p className="inline-flex items-center gap-2 text-xs text-muted-foreground">
                        <Coins className="size-4 text-gold" /> Ouro
                      </p>
                      <p className="mt-1 text-xl font-semibold">{sheet.gold}</p>
                    </div>
                    <div className="rounded-lg border border-border/80 bg-background/50 p-4">
                      <p className="text-xs text-muted-foreground">Itens carregados</p>
                      <p className="mt-1 text-xl font-semibold">
                        {sheet.inventory.reduce((total, item) => total + item.quantity, 0)}
                      </p>
                    </div>
                  </div>
                </section>
                <form
                  onSubmit={(event) => void saveName(event)}
                  className="fantasy-card flex flex-col gap-3 rounded-xl border p-4 sm:flex-row sm:items-end"
                >
                  <label
                    className="min-w-0 flex-1 space-y-1.5 text-sm"
                    htmlFor="sheet-character-name"
                  >
                    Renomear personagem
                    <Input
                      id="sheet-character-name"
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      maxLength={100}
                      required
                    />
                  </label>
                  <Button
                    type="submit"
                    disabled={savingName || name === sheet.name}
                    aria-busy={savingName}
                  >
                    {savingName ? "Salvando..." : "Salvar nome"}
                  </Button>
                </form>
              </TabsContent>

              <TabsContent value="attributes" className="space-y-5">
                <section className="fantasy-card rounded-2xl border p-5 sm:p-7">
                  <h2 className="font-serif text-xl font-semibold">Recursos</h2>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <ResourceBar
                      label="HP"
                      current={sheet.hp}
                      maximum={sheet.max_hp}
                      icon={Heart}
                      color="text-rose-400"
                    />
                    <ResourceBar
                      label="Mana"
                      current={sheet.mana}
                      maximum={sheet.max_mana}
                      icon={Zap}
                      color="text-sky-400"
                    />
                  </div>
                  <p className="mt-4 text-sm text-muted-foreground">
                    {sheet.xp} XP · {sheet.gold} ouro
                  </p>
                </section>
                <section className="fantasy-card rounded-2xl border p-5 sm:p-7">
                  <h2 className="font-serif text-xl font-semibold">Atributos</h2>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Pontos disponíveis para uma futura alocação: {sheet.attribute_points}
                  </p>
                  {Object.keys(sheet.attributes).length === 0 ? (
                    <div className="mt-4">
                      <EmptyState>Nenhum atributo foi registrado para este personagem.</EmptyState>
                    </div>
                  ) : (
                    <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      {Object.entries(sheet.attributes).map(([attribute, value]) => (
                        <div
                          key={attribute}
                          className="rounded-lg border border-border/80 bg-background/50 p-4"
                        >
                          <dt className="text-sm capitalize text-muted-foreground">
                            {attribute.replaceAll("_", " ")}
                          </dt>
                          <dd className="mt-1 font-semibold">
                            {typeof value === "string" ? value : JSON.stringify(value)}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  )}
                </section>
                <section className="fantasy-card rounded-2xl border p-5 sm:p-7">
                  <h2 className="font-serif text-xl font-semibold">Progressão recente</h2>
                  {sheet.progression_history.length === 0 ? (
                    <div className="mt-4">
                      <EmptyState>Nenhuma recompensa de progressão foi registrada.</EmptyState>
                    </div>
                  ) : (
                    <ol className="mt-4 space-y-3">
                      {sheet.progression_history.map((event) => (
                        <li
                          key={event.id}
                          className="rounded-lg border border-border/80 bg-background/50 p-4"
                        >
                          {event.level_after > event.level_before && (
                            <p
                              role="status"
                              className="mb-2 inline-flex items-center gap-2 text-sm font-semibold text-gold"
                            >
                              <Sparkles className="size-4" />
                              Evolução: nível {event.level_before} → {event.level_after}
                            </p>
                          )}
                          <p className="text-sm font-medium">
                            +{event.xp_awarded} XP
                            {event.gold_awarded > 0 ? ` · +${event.gold_awarded} ouro` : ""}
                          </p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            Origem:{" "}
                            {event.source_type === "narrative"
                              ? "aventura"
                              : event.source_type === "quest"
                                ? "missão"
                                : event.source_type === "world_reward"
                                  ? "recompensa do mundo"
                                  : event.source_type}
                            {event.source_name ? ` — ${event.source_name}` : ""}
                          </p>
                          {event.items.length > 0 && (
                            <p className="mt-1 text-sm text-foreground">
                              Itens:{" "}
                              {event.items
                                .map((item) => `${item.name} ×${item.quantity}`)
                                .join(", ")}
                            </p>
                          )}
                          {event.level_after > event.level_before && (
                            <p className="mt-1 text-xs text-muted-foreground">
                              +{event.max_hp_increase} HP máximo · +{event.max_mana_increase} mana
                              máxima · +{event.attribute_points_awarded} pontos de atributo
                            </p>
                          )}
                          <p className="mt-1 text-xs text-muted-foreground">
                            {new Date(event.created_at).toLocaleString("pt-BR")}
                          </p>
                        </li>
                      ))}
                    </ol>
                  )}
                </section>
              </TabsContent>

              <TabsContent value="inventory">
                {sheet.inventory.length === 0 ? (
                  <EmptyState>Seu inventário ainda está vazio.</EmptyState>
                ) : (
                  <>
                    <div className="mb-4 flex items-center gap-3">
                      <label className="text-sm text-muted-foreground" htmlFor="inventory-category">
                        Categoria
                      </label>
                      <select
                        id="inventory-category"
                        className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                        value={inventoryCategory}
                        onChange={(event) => setInventoryCategory(event.target.value)}
                      >
                        <option value="all">Todas</option>
                        <option value="carreira">Carreira</option>
                      </select>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      {sheet.inventory
                        .filter((item) => inventoryCategory === "all" || item.is_career)
                        .map((item) => (
                          <article
                            key={item.item_id}
                            className="fantasy-card rounded-xl border p-4"
                          >
                            <div className="flex gap-4">
                              {item.image_url ? (
                                <img
                                  src={item.image_url}
                                  alt=""
                                  className="size-16 rounded-lg object-cover"
                                />
                              ) : (
                                <span className="flex size-16 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                                  <Backpack className="size-6" />
                                </span>
                              )}
                              <div className="min-w-0">
                                <h2 className="font-semibold">{item.name}</h2>
                                <p className="text-xs capitalize text-muted-foreground">
                                  {item.rarity} · {item.category}
                                </p>
                                {item.is_career && (
                                  <span className="mt-2 inline-flex rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 text-xs text-primary">
                                    Subclasse de carreira
                                  </span>
                                )}
                                {item.is_career && item.origin["mode"] === "solo" && (
                                  <span className="mt-2 inline-flex rounded-full border border-gold/30 bg-gold/10 px-2.5 py-1 text-xs text-gold">
                                    Obtido no modo solo
                                  </span>
                                )}
                                {item.description && (
                                  <p className="mt-2 text-sm text-muted-foreground">
                                    {item.description}
                                  </p>
                                )}
                              </div>
                            </div>
                            <div className="mt-4 flex flex-wrap gap-2 text-xs">
                              <span className="rounded-full bg-muted px-2.5 py-1">
                                Quantidade: {item.quantity}
                              </span>
                              <span className="rounded-full bg-muted px-2.5 py-1">
                                Peso: {item.weight}
                              </span>
                              {item.is_equipped && (
                                <span className="rounded-full bg-primary/10 px-2.5 py-1 text-primary">
                                  Equipado{item.slot ? ` · ${item.slot}` : ""}
                                </span>
                              )}
                            </div>
                            <div className="mt-4">
                              {item.is_equipped ? (
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  disabled={equipmentBusyId === item.item_id}
                                  onClick={() => void unequipItem(item.item_id)}
                                >
                                  {equipmentBusyId === item.item_id ? "Removendo..." : "Desequipar"}
                                </Button>
                              ) : slotsForCategory(item.category).length > 0 ? (
                                <div className="flex items-center gap-2">
                                  <select
                                    aria-label={`Slot para ${item.name}`}
                                    className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                                    defaultValue={slotsForCategory(item.category)[0]}
                                    id={`equipment-slot-${item.item_id}`}
                                  >
                                    {slotsForCategory(item.category).map((slot) => (
                                      <option key={slot} value={slot}>
                                        {slotLabels[slot] ?? slot}
                                      </option>
                                    ))}
                                  </select>
                                  <Button
                                    type="button"
                                    size="sm"
                                    disabled={equipmentBusyId === item.item_id}
                                    onClick={() => {
                                      const selectedSlot = (
                                        document.getElementById(
                                          `equipment-slot-${item.item_id}`,
                                        ) as HTMLSelectElement | null
                                      )?.value;
                                      if (selectedSlot) void equipItem(item.item_id, selectedSlot);
                                    }}
                                  >
                                    {equipmentBusyId === item.item_id ? "Equipando..." : "Equipar"}
                                  </Button>
                                </div>
                              ) : null}
                            </div>
                          </article>
                        ))}
                    </div>
                  </>
                )}
              </TabsContent>

              <TabsContent value="skills">
                {sheet.skills.length === 0 ? (
                  <EmptyState>Nenhuma habilidade foi registrada para este personagem.</EmptyState>
                ) : (
                  <div className="grid gap-3 sm:grid-cols-2">
                    {sheet.skills.map((skill) => (
                      <article key={skill.id} className="fantasy-card rounded-xl border p-5">
                        <div className="flex items-start gap-3">
                          <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                            <Sparkles className="size-5" />
                          </span>
                          <div>
                            <h2 className="font-semibold">{skill.name}</h2>
                            <p className="text-xs capitalize text-muted-foreground">
                              {skill.category}
                            </p>
                          </div>
                        </div>
                        {skill.description && (
                          <p className="mt-3 text-sm leading-6 text-muted-foreground">
                            {skill.description}
                          </p>
                        )}
                        <p className="mt-3 text-xs text-muted-foreground">
                          Custo: {skill.mana_cost} mana · Alvo: {skill.target} · Recarga:{" "}
                          {skill.cooldown_seconds}s
                        </p>
                      </article>
                    ))}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="quests">
                {campaignQuests.length === 0 ? (
                  <EmptyState>Nenhuma missão publicada está disponível nesta campanha.</EmptyState>
                ) : (
                  <div className="space-y-3">
                    {campaignQuests.map((quest) => {
                      const objectiveProgress = quest.progress["objectives"];
                      const counts =
                        typeof objectiveProgress === "object" && objectiveProgress !== null
                          ? (objectiveProgress as Record<string, unknown>)
                          : {};
                      const rewardRecord = sheet.progression_history.find(
                        (event) => event.source_type === "quest" && event.source_id === quest.id,
                      );
                      const rewardItems = Array.isArray(quest.rewards["items"])
                        ? quest.rewards["items"].flatMap((rawItem) => {
                            if (
                              typeof rawItem !== "object" ||
                              rawItem === null ||
                              !("item_id" in rawItem) ||
                              typeof rawItem.item_id !== "string"
                            )
                              return [];
                            const item = sheet.inventory.find(
                              (inventoryItem) => inventoryItem.item_id === rawItem.item_id,
                            );
                            return [item?.name ?? "Item de recompensa"];
                          })
                        : [];
                      const skillNames = Array.isArray(quest.rewards["skill_ids"])
                        ? quest.rewards["skill_ids"].flatMap((id) => {
                            if (typeof id !== "string") return [];
                            const skill = sheet.skills.find((entry) => entry.id === id);
                            return skill ? [skill.name] : [];
                          })
                        : [];
                      return (
                        <article key={quest.id} className="fantasy-card rounded-xl border p-5">
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <h2 className="inline-flex items-center gap-2 font-semibold">
                              <BookOpen className="size-4 text-primary" /> {quest.title}
                            </h2>
                            <span className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-1 text-xs capitalize text-muted-foreground">
                              {quest.status === "completed" && (
                                <CheckCircle2 className="size-3 text-emerald-400" />
                              )}
                              {quest.status.replaceAll("_", " ")}
                            </span>
                          </div>
                          {quest.description && (
                            <p className="mt-3 text-sm leading-6 text-muted-foreground">
                              {quest.description}
                            </p>
                          )}
                          {quest.objectives.length > 0 && (
                            <ul className="mt-4 space-y-2">
                              {quest.objectives.map((objective) => {
                                const current = counts[objective.id];
                                const completed =
                                  typeof current === "number" && current >= objective.target;
                                return (
                                  <li
                                    key={objective.id}
                                    className="rounded-lg border border-border/70 p-3"
                                  >
                                    <p className="flex items-center justify-between gap-3 text-sm font-medium">
                                      <span>{objective.title}</span>
                                      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                                        {typeof current === "number"
                                          ? Math.min(current, objective.target)
                                          : 0}{" "}
                                        / {objective.target}
                                      </span>
                                    </p>
                                    {objective.description && (
                                      <p className="mt-1 text-xs text-muted-foreground">
                                        {objective.description}
                                      </p>
                                    )}
                                    {completed && (
                                      <p className="mt-1 text-xs text-emerald-400">
                                        Objetivo concluído
                                      </p>
                                    )}
                                  </li>
                                );
                              })}
                            </ul>
                          )}
                          {typeof quest.rewards["xp"] === "number" ||
                          typeof quest.rewards["gold"] === "number" ||
                          rewardItems.length > 0 ||
                          skillNames.length > 0 ? (
                            <p className="mt-3 text-xs text-muted-foreground">
                              {quest.status === "completed"
                                ? "Recompensas recebidas: "
                                : "Recompensas: "}
                              {typeof quest.rewards["xp"] === "number" && quest.rewards["xp"] > 0
                                ? `${quest.rewards["xp"]} XP`
                                : ""}
                              {typeof quest.rewards["gold"] === "number" &&
                              quest.rewards["gold"] > 0
                                ? `${typeof quest.rewards["xp"] === "number" && quest.rewards["xp"] > 0 ? " · " : ""}${quest.rewards["gold"]} ouro`
                                : ""}
                              {rewardItems.length > 0 ? ` · ${rewardItems.join(", ")}` : ""}
                              {skillNames.length > 0 ? ` · ${skillNames.join(", ")}` : ""}
                            </p>
                          ) : null}
                          {rewardRecord && (
                            <p className="mt-2 text-sm text-emerald-300">
                              Concedido: +{rewardRecord.xp_awarded} XP
                              {rewardRecord.gold_awarded > 0
                                ? ` · +${rewardRecord.gold_awarded} ouro`
                                : ""}
                              {rewardRecord.items.length > 0
                                ? ` · ${rewardRecord.items.map((item) => `${item.name} ×${item.quantity}`).join(", ")}`
                                : ""}
                            </p>
                          )}
                          {quest.status === "available" && (
                            <Button
                              type="button"
                              className="mt-4"
                              size="sm"
                              disabled={acceptingQuestId !== null}
                              onClick={() => void acceptQuest(quest.id)}
                            >
                              <Play className="mr-1 size-4" />
                              {acceptingQuestId === quest.id ? "Iniciando..." : "Aceitar missão"}
                            </Button>
                          )}
                        </article>
                      );
                    })}
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </>
        )}
      </div>
    </main>
  );
}
