import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Swords } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  getCombatAsset,
  getLatestCombat,
  listCombatEnemies,
  resolveCombatAction,
  startCombat,
  submitCombatAction,
} from "@/lib/combat-api";
import type {
  CombatEncounter,
  CombatEnemyOption,
  CombatEvent,
  CombatantState,
} from "@/lib/combat-api";
import type { Campaign, AuthUser } from "@/lib/auth-api";
import {
  createNonOverlappingPoll,
  type NonOverlappingPollState,
} from "@/lib/create-non-overlapping-poll";

type Props = { campaign: Campaign; user: AuthUser };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function describeEvent(event: CombatEvent): string {
  const payload = event.payload;
  if (event.type === "battle_started") return "A batalha começou.";
  if (event.type === "battle_finished") {
    return payload["result"] === "victory" ? "Vitória!" : "Derrota.";
  }
  if (event.type === "action_resolved") {
    const damage = typeof payload["damage"] === "number" ? payload["damage"] : 0;
    const healing = typeof payload["healing"] === "number" ? payload["healing"] : 0;
    return healing > 0 ? `Recuperou ${healing} HP.` : `Causou ${damage} de dano.`;
  }
  if (event.type === "turn_started") return "Novo turno.";
  if (event.type === "effect_tick") {
    return `Efeito contínuo: ${String(payload["damage"] ?? 0)} de dano.`;
  }
  if (event.type === "rewards_applied") return "Recompensas adicionadas à progressão.";
  return "A batalha avançou.";
}

function hasActionVisual(event: CombatEvent): boolean {
  const visual = event.payload["visual"];
  return (
    event.type === "action_started" &&
    typeof event.payload["action_id"] === "string" &&
    isRecord(visual) &&
    typeof visual["release_delay_ms"] === "number" &&
    Number.isFinite(visual["release_delay_ms"]) &&
    visual["release_delay_ms"] >= 0 &&
    typeof visual["animation_duration_ms"] === "number" &&
    Number.isFinite(visual["animation_duration_ms"]) &&
    visual["animation_duration_ms"] >= 1
  );
}

function CombatPortrait({
  campaignId,
  combatant,
}: {
  campaignId: string;
  combatant: CombatantState;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const assets = combatant.snapshot["assets"];
  const spriteId =
    isRecord(assets) && typeof assets["sprite"] === "string" ? assets["sprite"] : null;
  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;
    if (!spriteId) return;
    void getCombatAsset(campaignId, spriteId)
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (active) setUrl(null);
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [campaignId, spriteId]);
  return url ? (
    <img src={url} alt="" className="size-12 rounded-lg object-contain" />
  ) : (
    <span className="flex size-12 items-center justify-center rounded-lg bg-muted">
      <Swords className="size-5 text-muted-foreground" />
    </span>
  );
}

function CombatFrameCard({
  campaignId,
  combatant,
}: {
  campaignId: string;
  combatant: CombatantState;
}) {
  const frameTone = combatant.is_enemy
    ? "border-red-500/70 bg-red-500/5"
    : "border-blue-500/70 bg-blue-500/5";
  const activeTone = combatant.is_active ? "shadow-sm shadow-current/10" : "border-border";
  return (
    <article
      key={combatant.id}
      aria-label={combatant.is_enemy ? `Inimigo ${combatant.name}` : `Jogador ${combatant.name}`}
      className={`rounded-xl border p-3 ${frameTone} ${activeTone}`}
    >
      <div className="flex items-center gap-3">
        <CombatPortrait campaignId={campaignId} combatant={combatant} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">
            {combatant.name}
            {combatant.is_enemy ? " · Inimigo" : ""}
          </p>
          <div
            className="mt-2 h-2 overflow-hidden rounded-full bg-muted"
            aria-label={`HP ${combatant.name}`}
          >
            <div
              className="h-full bg-red-500 transition-[width]"
              style={{
                width: `${Math.max(0, Math.min(100, (100 * combatant.current_hp) / Math.max(1, combatant.max_hp)))}%`,
              }}
            />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            HP {combatant.current_hp}/{combatant.max_hp} · Mana {combatant.current_mana}/
            {combatant.max_mana}
          </p>
        </div>
      </div>
    </article>
  );
}

export function CombatPanel({ campaign, user }: Props) {
  const [encounter, setEncounter] = useState<CombatEncounter | null>(null);
  const [enemies, setEnemies] = useState<CombatEnemyOption[]>([]);
  const [chosenEnemy, setChosenEnemy] = useState("");
  const [selectedEnemyIds, setSelectedEnemyIds] = useState<string[]>([]);
  const [selectedTargetId, setSelectedTargetId] = useState("");
  const [selectedSkillId, setSelectedSkillId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [visualBusy, setVisualBusy] = useState(false);
  const [error, setError] = useState("");
  const [visualEvent, setVisualEvent] = useState<CombatEvent | null>(null);
  const [visualStep, setVisualStep] = useState(0);
  const [projectileLaunched, setProjectileLaunched] = useState(false);
  const [actorFile, setActorFile] = useState<Blob>();
  const [attackFile, setAttackFile] = useState<Blob>();
  const [visualReady, setVisualReady] = useState(false);
  const [assetError, setAssetError] = useState(false);
  const observedSequence = useRef(0);
  const observedEncounterId = useRef<string | null>(null);
  const visualEventRef = useRef<CombatEvent | null>(null);
  const visualQueue = useRef<CombatEvent[]>([]);
  const seenVisualSequences = useRef(new Set<number>());
  const resolvingActionIds = useRef(new Set<string>());
  const requestRevision = useRef(0);
  const actionInFlight = useRef(false);
  const pollState = useRef<NonOverlappingPollState>({ inFlight: false, nextTask: null });
  const ownMember = campaign.members.find((member) => member.user_id === user.id);
  const isOwner = campaign.owner_id === user.id;
  const activeCombatant = encounter?.combatants.find((item) => item.is_active);
  const isMyTurn =
    activeCombatant?.character_id !== null &&
    activeCombatant?.character_id === ownMember?.character_id;
  const ownSkills =
    isMyTurn && activeCombatant
      ? Object.entries(activeCombatant.snapshot["skills"] ?? {}).flatMap(([id, value]) =>
          isRecord(value) ? [{ id, name: String(value["name"] ?? "Habilidade"), value }] : [],
        )
      : [];
  const selectedSkill = ownSkills.find((skill) => skill.id === selectedSkillId)?.value;
  const additionalEffects = selectedSkill?.["additional_effects"];
  const isHealing = selectedSkill
    ? String(
        (isRecord(additionalEffects) && additionalEffects["effect_type"]) ||
          selectedSkill["skill_type"] ||
          "",
      )
        .toLowerCase()
        .match(/^(heal|healing|cura|curar)$/) !== null
    : false;
  const skillTargetType = String(selectedSkill?.["target_type"] ?? "").toLowerCase();
  const targetsSameSide =
    isHealing ||
    skillTargetType === "ally" ||
    skillTargetType === "friendly" ||
    skillTargetType === "self";
  const targets = (encounter?.combatants ?? []).filter(
    (item) =>
      item.current_hp > 0 &&
      (targetsSameSide ? !item.is_enemy : item.is_enemy !== (activeCombatant?.is_enemy ?? false)) &&
      (skillTargetType !== "self" || item.id === activeCombatant?.id),
  );
  const visual = useMemo(() => {
    const payload = visualEvent?.payload;
    const details = payload && isRecord(payload["visual"]) ? payload["visual"] : null;
    return details ? { details } : null;
  }, [visualEvent]);
  const visualActor = visual
    ? encounter?.combatants.find((item) => item.id === visual.details["actor_id"])
    : undefined;
  const visualTarget = visual
    ? encounter?.combatants.find((item) => item.id === visual.details["target_id"])
    : undefined;
  const projectileOnly = visual?.details["projectile_only"] === true;
  const projectileStart = visualActor?.is_enemy ? "80%" : "20%";
  const projectileEnd = visualActor?.is_enemy ? "20%" : "80%";
  const actorUrl = useMemo(() => (actorFile ? URL.createObjectURL(actorFile) : null), [actorFile]);
  const attackUrl = useMemo(
    () => (attackFile ? URL.createObjectURL(attackFile) : null),
    [attackFile],
  );
  useEffect(() => {
    return () => {
      if (actorUrl) URL.revokeObjectURL(actorUrl);
      if (attackUrl) URL.revokeObjectURL(attackUrl);
    };
  }, [actorUrl, attackUrl]);

  const showVisual = useCallback((event: CombatEvent) => {
    if (!hasActionVisual(event)) return;
    visualEventRef.current = event;
    setVisualEvent(event);
    setVisualStep(0);
    setActorFile(undefined);
    setAttackFile(undefined);
    setVisualReady(false);
    setAssetError(false);
    setVisualBusy(true);
  }, []);

  const finishVisual = useCallback(() => {
    const next = visualQueue.current.shift();
    if (next) {
      showVisual(next);
      return;
    }
    visualEventRef.current = null;
    setVisualEvent(null);
    setVisualBusy(false);
  }, [showVisual]);

  const receiveBattle = useCallback(
    (battle: CombatEncounter | null) => {
      if (battle === null) {
        setEncounter(null);
        return;
      }
      const newEncounter = observedEncounterId.current !== battle.id;
      if (newEncounter) {
        observedEncounterId.current = battle.id;
        observedSequence.current = 0;
        visualQueue.current = [];
        visualEventRef.current = null;
        seenVisualSequences.current.clear();
        setVisualEvent(null);
        setVisualBusy(false);
      } else if (battle.last_sequence < observedSequence.current) {
        return;
      }
      setEncounter((current) =>
        current?.id === battle.id && current.version > battle.version ? current : battle,
      );
      if (observedSequence.current === 0) {
        observedSequence.current = battle.last_sequence;
        const pending = battle.pending_action;
        const pendingId = isRecord(pending) ? pending["action_id"] : null;
        const pendingVisual = [...battle.events]
          .reverse()
          .find((event) => hasActionVisual(event) && event.payload["action_id"] === pendingId);
        if (pendingVisual) {
          seenVisualSequences.current.add(pendingVisual.sequence);
          showVisual(pendingVisual);
        }
        return;
      }
      const newVisuals = battle.events.filter((event) => {
        if (
          event.sequence <= observedSequence.current ||
          !hasActionVisual(event) ||
          seenVisualSequences.current.has(event.sequence)
        ) {
          return false;
        }
        seenVisualSequences.current.add(event.sequence);
        return true;
      });
      observedSequence.current = Math.max(observedSequence.current, battle.last_sequence);
      if (!newVisuals.length) return;
      visualQueue.current.push(...newVisuals);
      if (visualEventRef.current === null) {
        const next = visualQueue.current.shift();
        if (next) showVisual(next);
      }
    },
    [showVisual],
  );

  const refresh = useCallback(
    async (active: () => boolean) => {
      const revision = requestRevision.current;
      const [battle, availableEnemies] = await Promise.all([
        getLatestCombat(campaign.id),
        listCombatEnemies(campaign.id),
      ]);
      if (!active() || revision !== requestRevision.current) return;
      receiveBattle(battle);
      setEnemies(availableEnemies);
      setLoading(false);
      setError("");
    },
    [campaign.id, receiveBattle],
  );

  useEffect(() => {
    let active = true;
    const run = async () => {
      if (!active || document.visibilityState !== "visible") return;
      try {
        await refresh(() => active);
      } catch (requestError) {
        if (active)
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Não foi possível carregar a batalha.",
          );
        if (active) setLoading(false);
      }
    };
    const poll = createNonOverlappingPoll(run, pollState.current);
    void poll();
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void poll();
    }, 4_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [campaign.id, refresh]);

  useEffect(() => {
    let active = true;
    setActorFile(undefined);
    setAttackFile(undefined);
    setAssetError(false);
    setVisualReady(false);
    if (!visual) return;
    const actorAssetId =
      typeof visual.details["actor_animation_asset_id"] === "string"
        ? visual.details["actor_animation_asset_id"]
        : null;
    const attackAssetId =
      typeof visual.details["attack_asset_id"] === "string"
        ? visual.details["attack_asset_id"]
        : null;
    const load = async (assetId: string | null) => {
      if (!assetId) return undefined;
      try {
        return await getCombatAsset(campaign.id, assetId);
      } catch {
        if (active) setAssetError(true);
        return undefined;
      }
    };
    void Promise.all([load(actorAssetId), load(attackAssetId)]).then(([actor, attack]) => {
      if (!active) return;
      setActorFile(actor);
      setAttackFile(attack);
      setVisualReady(true);
    });
    return () => {
      active = false;
    };
  }, [campaign.id, visualEvent, visual]);

  useEffect(() => {
    if (visualStep !== 1) {
      setProjectileLaunched(false);
      return;
    }
    const frame = window.requestAnimationFrame(() => setProjectileLaunched(true));
    return () => window.cancelAnimationFrame(frame);
  }, [visualEvent, visualStep]);

  useEffect(() => {
    const actionId = visualEvent?.payload["action_id"];
    const encounterId = encounter?.id;
    if (!visualBusy || !visualReady || typeof actionId !== "string" || !visual || !encounterId) {
      return;
    }
    const releaseDelay = visual.details["release_delay_ms"] as number;
    const animationDuration = visual.details["animation_duration_ms"] as number;
    const attackTimer = window.setTimeout(() => setVisualStep(1), releaseDelay);
    const resolveTimer = window.setTimeout(() => {
      if (resolvingActionIds.current.has(actionId)) return;
      resolvingActionIds.current.add(actionId);
      void resolveCombatAction(campaign.id, encounterId, actionId)
        .then((battle) => {
          receiveBattle(battle);
          finishVisual();
        })
        .catch((requestError) => {
          resolvingActionIds.current.delete(actionId);
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Não foi possível resolver a ação confirmada.",
          );
        });
    }, releaseDelay + animationDuration);
    return () => {
      window.clearTimeout(attackTimer);
      window.clearTimeout(resolveTimer);
    };
  }, [
    campaign.id,
    encounter?.id,
    finishVisual,
    receiveBattle,
    visual,
    visualEvent,
    visualBusy,
    visualReady,
  ]);

  const start = async () => {
    if (!selectedEnemyIds.length || busy) return;
    const revision = ++requestRevision.current;
    setBusy(true);
    setError("");
    try {
      const battle = await startCombat(campaign.id, selectedEnemyIds);
      if (revision !== requestRevision.current) return;
      requestRevision.current += 1;
      receiveBattle(battle);
      setSelectedEnemyIds([]);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível iniciar a batalha.",
      );
    } finally {
      requestRevision.current += 1;
      setBusy(false);
    }
  };

  const act = async (action: "attack" | "skill" | "end_turn") => {
    if (!encounter || !activeCombatant || busy || visualBusy || actionInFlight.current) return;
    if (action !== "end_turn" && !selectedTargetId) return;
    actionInFlight.current = true;
    const revision = ++requestRevision.current;
    setBusy(true);
    setError("");
    try {
      const battle = await submitCombatAction(campaign.id, encounter.id, {
        action_id: crypto.randomUUID(),
        action,
        ...(action === "end_turn" ? {} : { target_id: selectedTargetId }),
        ...(action === "skill" ? { skill_id: selectedSkillId } : {}),
      });
      if (revision !== requestRevision.current) return;
      requestRevision.current += 1;
      receiveBattle(battle);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Não foi possível executar a ação.",
      );
    } finally {
      requestRevision.current += 1;
      setBusy(false);
      actionInFlight.current = false;
    }
  };

  const addEnemy = () => {
    if (chosenEnemy) setSelectedEnemyIds((current) => [...current, chosenEnemy]);
  };

  if (loading) {
    return (
      <section className="mt-8 rounded-xl border p-5 text-sm text-muted-foreground">
        Carregando combate...
      </section>
    );
  }

  const activeBattle = encounter?.status === "in_progress";
  const eventLog = encounter?.events.slice(-8).reverse() ?? [];
  const combatants = encounter?.combatants ?? [];

  return (
    <section
      className="mt-8 rounded-2xl border border-primary/25 bg-card/60 p-4 sm:p-6"
      aria-label="Combate"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Combate</p>
          <h2 className="mt-1 font-serif text-2xl font-semibold">
            {activeBattle ? encounter?.title : "Preparar batalha"}
          </h2>
        </div>
        {activeBattle && (
          <span className="rounded-full border px-3 py-1 text-sm">
            Rodada {encounter?.round} · {activeCombatant?.name ?? "Preparando turno"}
          </span>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {!activeBattle && isOwner && campaign.status === "in_progress" && (
        <div className="mt-5 grid gap-3 sm:grid-cols-[1fr_auto]">
          <div className="flex min-w-0 gap-2">
            <select
              aria-label="Inimigo disponível"
              className="h-10 min-w-0 flex-1 rounded-md border border-input bg-background px-3"
              value={chosenEnemy}
              onChange={(event) => setChosenEnemy(event.target.value)}
            >
              <option value="">Selecione um inimigo publicado</option>
              {enemies.map((enemy) => (
                <option key={enemy.id} value={enemy.id}>
                  {enemy.name} · HP {enemy.hp}
                </option>
              ))}
            </select>
            <Button type="button" variant="outline" onClick={addEnemy} disabled={!chosenEnemy}>
              Adicionar
            </Button>
          </div>
          <Button
            type="button"
            onClick={() => void start()}
            disabled={!selectedEnemyIds.length || busy}
          >
            {busy ? "Iniciando..." : "Iniciar batalha"}
          </Button>
          {selectedEnemyIds.length > 0 && (
            <ul className="flex flex-wrap gap-2 text-sm sm:col-span-2">
              {selectedEnemyIds.map((id, index) => {
                const enemy = enemies.find((candidate) => candidate.id === id);
                return (
                  <li
                    key={`${id}-${index}`}
                    className="flex items-center gap-2 rounded-full bg-muted px-3 py-1"
                  >
                    {enemy?.name ?? "Inimigo"}
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-foreground"
                      aria-label={`Remover ${enemy?.name ?? "inimigo"} ${index + 1}`}
                      onClick={() =>
                        setSelectedEnemyIds((current) =>
                          current.filter((_, itemIndex) => itemIndex !== index),
                        )
                      }
                    >
                      ×
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          {enemies.length === 0 && (
            <p className="text-sm text-muted-foreground sm:col-span-2">
              Não há inimigos ativos com perfil H.3 disponível.
            </p>
          )}
        </div>
      )}

      {encounter && (
        <>
          {encounter.status !== "in_progress" && (
            <p className="mt-4 rounded-lg border p-3 font-medium">
              {encounter.result === "victory"
                ? "Vitória. Recompensas processadas pelo backend."
                : "Batalha encerrada por derrota."}
            </p>
          )}
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {combatants.map((combatant) => (
              <CombatFrameCard key={combatant.id} campaignId={campaign.id} combatant={combatant} />
            ))}
          </div>

          {activeBattle && isMyTurn && (
            <div className="mt-5 grid gap-3 rounded-xl border bg-background/50 p-4 lg:grid-cols-[1fr_1fr_auto_auto]">
              <select
                aria-label="Habilidade de combate"
                className="h-10 rounded-md border border-input bg-background px-3"
                value={selectedSkillId}
                onChange={(event) => setSelectedSkillId(event.target.value)}
              >
                <option value="">Ataque físico</option>
                {ownSkills.map((skill) => (
                  <option key={skill.id} value={skill.id}>
                    {skill.name} · Mana {String(skill.value["mana_cost"] ?? 0)}
                  </option>
                ))}
              </select>
              <select
                aria-label="Alvo do combate"
                className="h-10 rounded-md border border-input bg-background px-3"
                value={selectedTargetId}
                onChange={(event) => setSelectedTargetId(event.target.value)}
              >
                <option value="">Selecione o alvo</option>
                {targets.map((target) => (
                  <option key={target.id} value={target.id}>
                    {target.name} · HP {target.current_hp}/{target.max_hp}
                  </option>
                ))}
              </select>
              <Button
                type="button"
                disabled={busy || visualBusy || !selectedTargetId}
                onClick={() => void act(selectedSkillId ? "skill" : "attack")}
              >
                {busy ? "Resolvendo..." : selectedSkillId ? "Usar habilidade" : "Atacar"}
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={busy || visualBusy}
                onClick={() => void act("end_turn")}
              >
                Encerrar turno
              </Button>
              {visualBusy && (
                <p role="status" className="text-sm text-muted-foreground sm:col-span-4">
                  Reproduzindo a ação e aguardando a resolução do servidor...
                </p>
              )}
            </div>
          )}

          {visual && visualEvent && (
            <div
              className="mt-5 rounded-xl border bg-background/50 p-4"
              aria-live="polite"
              aria-label="Animação da ação de combate"
            >
              <p className="mb-3 text-sm font-medium">
                {visualStep === 0
                  ? projectileOnly
                    ? "Preparação do projétil"
                    : "Animação do personagem"
                  : "Projétil em movimento"}
              </p>
              <div
                key={String(visualEvent.payload["action_id"])}
                className="relative flex min-h-40 items-center justify-between overflow-hidden rounded-lg bg-muted/40 px-4 sm:px-8"
              >
                {visualActor && (
                  <div
                    className={`z-10 flex w-24 flex-col items-center gap-2 text-center ${
                      visualActor.is_enemy ? "order-2" : "order-1"
                    }`}
                  >
                    {visualStep === 0 && actorUrl && !projectileOnly ? (
                      <img src={actorUrl} alt="" className="size-16 object-contain" />
                    ) : (
                      <CombatPortrait campaignId={campaign.id} combatant={visualActor} />
                    )}
                    <span className="max-w-24 truncate text-xs font-medium">
                      {visualActor.name}
                    </span>
                  </div>
                )}
                {visualTarget && (
                  <div
                    className={`z-10 flex w-24 flex-col items-center gap-2 text-center ${
                      visualActor?.is_enemy ? "order-1" : "order-2"
                    }`}
                  >
                    <CombatPortrait campaignId={campaign.id} combatant={visualTarget} />
                    <span className="max-w-24 truncate text-xs font-medium">
                      {visualTarget.name}
                    </span>
                  </div>
                )}
                {visualStep === 1 && attackUrl && (
                  <img
                    src={attackUrl}
                    alt={`Projétil de ${visualActor?.name ?? "quem ataca"}`}
                    className="absolute top-1/2 z-20 size-12 -translate-x-1/2 -translate-y-1/2 object-contain"
                    style={{
                      left: projectileLaunched ? projectileEnd : projectileStart,
                      transition: `left ${String(visual.details["animation_duration_ms"])}ms ease-in-out`,
                    }}
                  />
                )}
              </div>
              <p role="status" className="mt-3 text-xs text-muted-foreground">
                {visualStep === 0
                  ? projectileOnly
                    ? `${String(visualEvent.payload["actor_name"] ?? "Atacante")} prepara o projétil.`
                    : `${String(visualEvent.payload["actor_name"] ?? "Atacante")} prepara o ataque.`
                  : attackUrl
                    ? `Projétil de ${String(visualEvent.payload["actor_name"] ?? "Atacante")} segue para ${String(visualEvent.payload["target_name"] ?? "alvo")}.`
                    : `A ação de ${String(visualEvent.payload["actor_name"] ?? "Atacante")} será contabilizada pelo servidor.`}
              </p>
            </div>
          )}
          {assetError && (
            <p role="status" className="mt-3 text-sm text-muted-foreground">
              Um GIF está indisponível; a ação continuará com o fallback visual.
            </p>
          )}

          <ol
            className="mt-5 max-h-40 space-y-1 overflow-y-auto rounded-xl border bg-background/40 p-3 text-sm"
            aria-label="Histórico do combate"
          >
            {eventLog.map((event) => (
              <li key={event.sequence} className="flex justify-between gap-3">
                <span>{describeEvent(event)}</span>
                <span className="shrink-0 text-xs text-muted-foreground">#{event.sequence}</span>
              </li>
            ))}
            {eventLog.length === 0 && (
              <li className="text-muted-foreground">O histórico aparecerá aqui.</li>
            )}
          </ol>
        </>
      )}
    </section>
  );
}
