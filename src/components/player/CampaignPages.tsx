import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  BookOpen,
  Check,
  CircleUserRound,
  Copy,
  DoorOpen,
  LoaderCircle,
  LogOut,
  Play,
  Plus,
  RefreshCw,
  Shield,
  Users,
  Wifi,
  WifiOff,
} from "lucide-react";

import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Textarea } from "../ui/textarea";
import { CharacterSheet } from "./CharacterSheet";
import { CombatPanel } from "./CombatPanel";
import {
  createNonOverlappingPoll,
  type NonOverlappingPollState,
} from "../../lib/create-non-overlapping-poll";
import type { AuthUser, Campaign, CampaignSummary, SoloCharacter } from "../../lib/auth-api";
import {
  createCampaign,
  createSoloCharacter,
  castNarrativeVote,
  getDiscordStatus,
  getNarrativeGame,
  getCampaign,
  joinCampaign,
  leaveCampaign,
  listCampaigns,
  listSoloCharacters,
  pauseCampaign,
  resumeCampaign,
  startCampaign,
  selectSoloCharacter,
  startDiscordLink,
  updateCampaignCharacter,
  updateCampaignPresence,
  updateCampaignReady,
  type NarrativeGame,
} from "../../lib/auth-api";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function CampaignStatus({ status }: { status: string }) {
  const active = status === "in_progress";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
        active
          ? "border-gold/30 bg-gold/10 text-gold"
          : "border-primary/30 bg-primary/10 text-primary"
      }`}
    >
      <span className={`size-1.5 rounded-full ${active ? "bg-gold" : "bg-primary"}`} />
      {active
        ? "Em andamento"
        : status === "paused"
          ? "Pausada"
          : status === "closed"
            ? "Encerrada"
            : "Aguardando"}
    </span>
  );
}

function CampaignCard({
  campaign,
  onOpen,
  onRejoin,
}: {
  campaign: CampaignSummary;
  onOpen: () => void;
  onRejoin: () => void;
}) {
  const hasLeft = campaign.membership_status !== "active";
  return (
    <article className="fantasy-card rounded-xl border p-5 transition-colors">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-serif text-lg font-semibold text-foreground">{campaign.title}</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Proprietário da sala: {campaign.owner_display_name}
          </p>
        </div>
        <CampaignStatus status={campaign.status} />
      </div>
      {campaign.description && (
        <p className="mt-4 line-clamp-2 text-sm leading-6 text-muted-foreground">
          {campaign.description}
        </p>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <Users className="size-3.5" />
          {campaign.participant_count}/{campaign.max_players} participantes
        </span>
        <span className="font-mono tracking-wider">{campaign.join_code}</span>
        {hasLeft && <span>Você saiu desta sala</span>}
      </div>
      <div className="mt-5">
        {hasLeft ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onRejoin}
            disabled={campaign.status === "closed"}
          >
            Reentrar pelo código
          </Button>
        ) : (
          <Button type="button" variant="outline" size="sm" onClick={onOpen}>
            Abrir lobby
          </Button>
        )}
      </div>
    </article>
  );
}

export function CampaignsHomePage({
  user,
  onLogout,
}: {
  user: AuthUser;
  onLogout: () => Promise<void>;
}) {
  const navigate = useNavigate();
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"create" | "join" | "rejoin" | "logout" | "">("");
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [maxPlayers, setMaxPlayers] = useState(7);
  const [solo, setSolo] = useState(false);
  const [difficulty, setDifficulty] = useState<"normal" | "hard" | "legendary">("normal");
  const [joinCode, setJoinCode] = useState("");
  const [allowVoteChange, setAllowVoteChange] = useState(true);
  const [voteDeadlineSeconds, setVoteDeadlineSeconds] = useState("");
  const [tieBreaker, setTieBreaker] = useState<"unresolved" | "choice_order">("unresolved");
  const [discordLinked, setDiscordLinked] = useState(false);
  const [campaignModeFilter, setCampaignModeFilter] = useState<"all" | "solo" | "multiplayer">(
    "all",
  );
  const [deviceNotificationsEnabled, setDeviceNotificationsEnabled] = useState(false);
  const notificationsEnabledRef = useRef(false);
  const notificationStatuses = useRef<Map<string, string> | null>(null);
  const refreshPollState = useRef<NonOverlappingPollState>({
    inFlight: false,
    nextTask: null,
  });

  async function refreshCampaigns(signal?: AbortSignal) {
    try {
      const currentCampaigns = await listCampaigns(signal);
      const previousStatuses = notificationStatuses.current;
      if (
        previousStatuses &&
        notificationsEnabledRef.current &&
        "Notification" in window &&
        Notification.permission === "granted" &&
        document.visibilityState !== "visible"
      ) {
        for (const campaign of currentCampaigns) {
          const previousStatus = previousStatuses.get(campaign.id);
          if (previousStatus && previousStatus !== campaign.status) {
            const notice = new Notification(`Campanha atualizada: ${campaign.title}`, {
              body:
                campaign.status === "in_progress"
                  ? "A aventura está em andamento."
                  : campaign.status === "closed"
                    ? "A campanha foi encerrada."
                    : `Status: ${campaign.status}.`,
              tag: `campaign-${campaign.id}-${campaign.status}`,
            });
            notice.onclick = () => {
              window.focus();
              void navigate({
                to: "/campaigns/$campaignId",
                params: { campaignId: campaign.id },
              });
            };
          }
        }
      }
      notificationStatuses.current = new Map(
        currentCampaigns.map((campaign) => [campaign.id, campaign.status]),
      );
      setCampaigns(currentCampaigns);
      setError("");
    } catch (requestError) {
      if (!signal?.aborted) {
        setError(errorMessage(requestError, "Não foi possível carregar suas campanhas."));
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }

  useEffect(() => {
    const enabled = window.localStorage.getItem("campaign-device-notifications") === "enabled";
    notificationsEnabledRef.current = enabled;
    setDeviceNotificationsEnabled(
      enabled && "Notification" in window && Notification.permission === "granted",
    );
  }, []);

  async function toggleDeviceNotifications() {
    if (deviceNotificationsEnabled) {
      window.localStorage.removeItem("campaign-device-notifications");
      notificationsEnabledRef.current = false;
      setDeviceNotificationsEnabled(false);
      return;
    }
    if (!("Notification" in window)) {
      setError("Este navegador não oferece notificações do sistema.");
      return;
    }
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      setError("A permissão para notificações não foi concedida.");
      return;
    }
    window.localStorage.setItem("campaign-device-notifications", "enabled");
    notificationsEnabledRef.current = true;
    setDeviceNotificationsEnabled(true);
  }

  useEffect(() => {
    void getDiscordStatus()
      .then((status) => setDiscordLinked(status.linked))
      .catch(() => setDiscordLinked(false));
  }, []);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const isVisible = () => document.visibilityState === "visible";
    const refreshIfIdle = createNonOverlappingPoll(async () => {
      if (active && (isVisible() || notificationsEnabledRef.current)) {
        await refreshCampaigns(controller.signal);
      }
    }, refreshPollState.current);
    const refreshWhenVisible = () => {
      if (active && (isVisible() || notificationsEnabledRef.current)) void refreshIfIdle();
    };
    document.addEventListener("visibilitychange", refreshWhenVisible);
    refreshWhenVisible();
    const timer = window.setInterval(refreshWhenVisible, 10_000);
    return () => {
      active = false;
      controller.abort();
      document.removeEventListener("visibilitychange", refreshWhenVisible);
      window.clearInterval(timer);
    };
  }, []);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("create");
    setError("");
    try {
      const campaign = await createCampaign({
        title,
        description,
        max_players: maxPlayers,
        solo,
        difficulty,
        voting_settings: {
          allow_vote_change: allowVoteChange,
          deadline_seconds: voteDeadlineSeconds ? Number(voteDeadlineSeconds) : null,
          tie_breaker: tieBreaker,
        },
      });
      await navigate({
        to: "/campaigns/$campaignId",
        params: { campaignId: campaign.id },
      });
    } catch (requestError) {
      setError(errorMessage(requestError, "Não foi possível criar a campanha."));
    } finally {
      setBusy("");
    }
  }

  async function handleJoin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("join");
    setError("");
    try {
      const campaign = await joinCampaign(joinCode);
      await navigate({
        to: "/campaigns/$campaignId",
        params: { campaignId: campaign.id },
      });
    } catch (requestError) {
      setError(errorMessage(requestError, "Não foi possível entrar na sala."));
    } finally {
      setBusy("");
    }
  }

  async function handleRejoin(campaign: CampaignSummary) {
    setBusy("rejoin");
    setError("");
    try {
      const joined = await joinCampaign(campaign.join_code);
      await navigate({
        to: "/campaigns/$campaignId",
        params: { campaignId: joined.id },
      });
    } catch (requestError) {
      setError(errorMessage(requestError, "Não foi possível retornar à sala."));
      await refreshCampaigns();
    } finally {
      setBusy("");
    }
  }

  async function handleLogout() {
    setBusy("logout");
    setError("");
    try {
      await onLogout();
    } catch (requestError) {
      setError(errorMessage(requestError, "Não foi possível encerrar a sessão."));
      setBusy("");
    }
  }

  const filteredCampaigns = campaigns.filter((campaign) =>
    campaignModeFilter === "all"
      ? true
      : campaignModeFilter === "solo"
        ? campaign.solo
        : !campaign.solo,
  );
  const waiting = filteredCampaigns.filter((campaign) => campaign.status === "waiting");
  const inProgress = filteredCampaigns.filter((campaign) => campaign.status === "in_progress");
  const closed = filteredCampaigns.filter((campaign) => campaign.status === "closed");

  return (
    <main className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-border/70 bg-background/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <Link to="/" className="flex items-center gap-3 text-foreground">
            <span className="brand-seal flex size-10 items-center justify-center rounded-xl text-gold">
              <BookOpen className="size-5" />
            </span>
            <span className="font-serif font-semibold tracking-wide">Crônicas do Reino</span>
          </Link>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-muted-foreground sm:inline">
              {user.display_name}
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void toggleDeviceNotifications()}
            >
              {deviceNotificationsEnabled ? "Notificações ativadas" : "Ativar notificações"}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={discordLinked}
              onClick={() =>
                void startDiscordLink().catch((requestError) =>
                  setError(
                    errorMessage(requestError, "Não foi possível iniciar o vínculo com Discord."),
                  ),
                )
              }
            >
              {discordLinked ? "Discord vinculado" : "Vincular Discord"}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => void handleLogout()}>
              <LogOut className="size-4" />
              Sair
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-5 py-8 sm:px-8 sm:py-12">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
              Área do jogador
            </p>
            <h1 className="mt-2 font-serif text-3xl font-semibold text-foreground sm:text-4xl">
              Suas campanhas
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Crie uma campanha para reunir seu grupo ou entre em uma sala com o convite recebido.
              Acompanhe aqui as campanhas aguardando participantes, em andamento ou encerradas.
            </p>
          </div>
          <Link to="/" className="text-sm text-muted-foreground transition hover:text-foreground">
            Voltar ao início
          </Link>
        </div>
        <div className="mb-6 flex flex-wrap gap-2" aria-label="Filtrar campanhas por modo">
          {(
            [
              ["all", "Todas"],
              ["solo", "Solo"],
              ["multiplayer", "Multiplayer"],
            ] as const
          ).map(([value, label]) => (
            <Button
              key={value}
              type="button"
              size="sm"
              variant={campaignModeFilter === value ? "default" : "outline"}
              onClick={() => setCampaignModeFilter(value)}
            >
              {label}
            </Button>
          ))}
        </div>

        {error && (
          <p
            role="alert"
            className="mb-6 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
          >
            {error}
          </p>
        )}

        <section
          aria-label="Criar ou entrar em uma campanha"
          className="mb-10 grid gap-4 lg:grid-cols-2"
        >
          <form
            id="criar-campanha"
            onSubmit={(event) => void handleCreate(event)}
            className="fantasy-card rounded-2xl border p-5 sm:p-6"
          >
            <div className="mb-5 flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Plus className="size-5" />
              </span>
              <div>
                <h2 className="font-semibold text-foreground">Criar campanha</h2>
                <p className="text-xs text-muted-foreground">
                  Dê um nome à campanha; você será o proprietário da sala.
                </p>
              </div>
            </div>
            <div className="space-y-3">
              <label className="block space-y-1.5 text-sm" htmlFor="campaign-title">
                Nome da campanha
                <Input
                  id="campaign-title"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  maxLength={160}
                  required
                />
                <span className="text-xs text-muted-foreground">
                  Escolha um nome que ajude seu grupo a reconhecer a aventura.
                </span>
              </label>
              <label className="block space-y-1.5 text-sm" htmlFor="campaign-description">
                Descrição <span className="text-muted-foreground">(opcional)</span>
                <Textarea
                  id="campaign-description"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  maxLength={5000}
                  rows={3}
                  placeholder="Contexto ou objetivo da aventura para o grupo..."
                />
              </label>
              <label className="flex items-start gap-2 text-sm" htmlFor="campaign-solo">
                <input
                  id="campaign-solo"
                  type="checkbox"
                  className="mt-1 accent-primary"
                  checked={solo}
                  onChange={(event) => setSolo(event.target.checked)}
                />
                <span>Criar campanha solo. Apenas você participará da aventura.</span>
              </label>
              {solo && (
                <label className="block space-y-1.5 text-sm" htmlFor="campaign-difficulty">
                  Dificuldade da aventura
                  <select
                    id="campaign-difficulty"
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground"
                    value={difficulty}
                    onChange={(event) =>
                      setDifficulty(event.target.value as "normal" | "hard" | "legendary")
                    }
                  >
                    <option value="normal">Normal</option>
                    <option value="hard">Difícil</option>
                    <option value="legendary">Lendário</option>
                  </select>
                </label>
              )}
              <label className="block space-y-1.5 text-sm" htmlFor="campaign-max-players">
                Limite de participantes (inclui você)
                <select
                  id="campaign-max-players"
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground"
                  value={maxPlayers}
                  disabled={solo}
                  onChange={(event) => setMaxPlayers(Number(event.target.value))}
                >
                  {[3, 4, 5, 6, 7].map((count) => (
                    <option key={count} value={count}>
                      {count} participantes
                    </option>
                  ))}
                </select>
                <span className="text-xs text-muted-foreground">
                  A campanha exige ao menos 3 participantes para iniciar.
                </span>
              </label>
              {!solo && (
                <label className="flex items-start gap-2 text-sm" htmlFor="campaign-vote-change">
                  <input
                    id="campaign-vote-change"
                    type="checkbox"
                    className="mt-1 accent-primary"
                    checked={allowVoteChange}
                    onChange={(event) => setAllowVoteChange(event.target.checked)}
                  />
                  <span>
                    Permitir que cada jogador altere seu voto enquanto a votação estiver aberta.
                  </span>
                </label>
              )}
              {!solo && (
                <label className="block space-y-1.5 text-sm" htmlFor="campaign-vote-deadline">
                  Prazo de votação em segundos{" "}
                  <span className="text-muted-foreground">(opcional)</span>
                  <Input
                    id="campaign-vote-deadline"
                    type="number"
                    min={1}
                    step={1}
                    value={voteDeadlineSeconds}
                    onChange={(event) => setVoteDeadlineSeconds(event.target.value)}
                    placeholder="Sem prazo: encerra quando todos votarem"
                  />
                </label>
              )}
              {!solo && (
                <label className="block space-y-1.5 text-sm" htmlFor="campaign-tie-breaker">
                  Desempate
                  <select
                    id="campaign-tie-breaker"
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground"
                    value={tieBreaker}
                    onChange={(event) =>
                      setTieBreaker(
                        event.target.value === "choice_order" ? "choice_order" : "unresolved",
                      )
                    }
                  >
                    <option value="unresolved">Registrar empate, sem avançar</option>
                    <option value="choice_order">Escolha de menor ordem no Painel do Mestre</option>
                  </select>
                </label>
              )}
              <Button type="submit" className="w-full" disabled={busy !== ""}>
                {busy === "create" ? <LoaderCircle className="animate-spin" /> : <Plus />}
                {busy === "create" ? "Criando campanha..." : "Criar campanha"}
              </Button>
            </div>
          </form>

          <form
            id="entrar-campanha"
            onSubmit={(event) => void handleJoin(event)}
            className="fantasy-card rounded-2xl border p-5 sm:p-6"
          >
            <div className="mb-5 flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-xl bg-gold/10 text-gold">
                <DoorOpen className="size-5" />
              </span>
              <div>
                <h2 className="font-semibold text-foreground">Entrar por código</h2>
                <p className="text-xs text-muted-foreground">
                  Use o convite compartilhado pelo proprietário da sala.
                </p>
              </div>
            </div>
            <label className="block space-y-1.5 text-sm" htmlFor="campaign-join-code">
              Código da sala
              <Input
                id="campaign-join-code"
                value={joinCode}
                onChange={(event) => setJoinCode(event.target.value.toUpperCase())}
                maxLength={32}
                className="font-mono uppercase tracking-widest"
                aria-describedby="campaign-join-code-help"
                autoComplete="off"
                spellCheck={false}
                required
              />
            </label>
            <p
              id="campaign-join-code-help"
              className="mt-3 text-xs leading-5 text-muted-foreground"
            >
              Cole o código exatamente como recebeu. Ele funciona como convite para a sala; peça ao
              proprietário se não tiver um. Seu personagem e seu progresso são vinculados a esta
              campanha.
            </p>
            <Button type="submit" variant="outline" className="mt-5 w-full" disabled={busy !== ""}>
              {busy === "join" ? <LoaderCircle className="animate-spin" /> : <DoorOpen />}
              {busy === "join" ? "Entrando na campanha..." : "Entrar na campanha"}
            </Button>
          </form>
        </section>

        <section id="minhas-campanhas" aria-label="Minhas campanhas" className="space-y-8">
          {loading && (
            <p role="status" aria-live="polite" className="text-sm text-muted-foreground">
              <RefreshCw className="mr-2 inline size-4 animate-spin" />
              Carregando suas campanhas...
            </p>
          )}
          <CampaignGroup
            title="Aguardando participantes"
            campaigns={waiting}
            loading={loading}
            onOpen={(campaign) =>
              void navigate({
                to: "/campaigns/$campaignId",
                params: { campaignId: campaign.id },
              })
            }
            onRejoin={(campaign) => void handleRejoin(campaign)}
          />
          <CampaignGroup
            title="Campanhas em andamento"
            campaigns={inProgress}
            loading={loading}
            onOpen={(campaign) =>
              void navigate({
                to: "/campaigns/$campaignId",
                params: { campaignId: campaign.id },
              })
            }
            onRejoin={(campaign) => void handleRejoin(campaign)}
          />
          <CampaignGroup
            title="Campanhas encerradas"
            campaigns={closed}
            loading={loading}
            onOpen={(campaign) =>
              void navigate({
                to: "/campaigns/$campaignId",
                params: { campaignId: campaign.id },
              })
            }
            onRejoin={(campaign) => void handleRejoin(campaign)}
          />
          {!loading && !error && campaigns.length === 0 && (
            <div className="rounded-2xl border border-dashed border-border px-6 py-10 text-center">
              <CircleUserRound className="mx-auto size-8 text-muted-foreground" />
              <p className="mt-3 font-medium text-foreground">Sua jornada ainda não começou</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Crie uma campanha para seu grupo ou entre usando um código de convite que já
                recebeu.
              </p>
              <div className="mt-5 flex flex-wrap justify-center gap-3">
                <a
                  href="#criar-campanha"
                  className="inline-flex min-h-11 items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                >
                  Criar campanha
                </a>
                <a
                  href="#entrar-campanha"
                  className="inline-flex min-h-11 items-center justify-center rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                >
                  Tenho um convite
                </a>
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function CampaignGroup({
  title,
  campaigns,
  loading,
  onOpen,
  onRejoin,
}: {
  title: string;
  campaigns: CampaignSummary[];
  loading: boolean;
  onOpen: (campaign: CampaignSummary) => void;
  onRejoin: (campaign: CampaignSummary) => void;
}) {
  if (!loading && campaigns.length === 0) return null;
  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-serif text-xl font-semibold text-foreground">{title}</h2>
        {loading && <RefreshCw className="size-4 animate-spin text-muted-foreground" />}
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {campaigns.map((campaign) => (
          <CampaignCard
            key={campaign.id}
            campaign={campaign}
            onOpen={() => onOpen(campaign)}
            onRejoin={() => onRejoin(campaign)}
          />
        ))}
      </div>
    </section>
  );
}

function NarrativeGamePanel({
  game,
  userId,
  busy,
  onVote,
  solo,
}: {
  game: NarrativeGame;
  userId: string;
  busy: boolean;
  onVote: (choiceId: string) => void;
  solo: boolean;
}) {
  const vote = game.vote;
  const previousResult = game.last_result;
  const previousChoice =
    previousResult !== null && typeof previousResult["choice_label"] === "string"
      ? previousResult["choice_label"]
      : null;
  const rawConsequence = previousResult?.["consequences"];
  const previousConsequence =
    typeof rawConsequence === "object" && rawConsequence !== null && !Array.isArray(rawConsequence)
      ? rawConsequence
      : null;
  const consequenceDescription =
    previousConsequence !== null &&
    !Array.isArray(previousConsequence) &&
    "description" in previousConsequence &&
    typeof previousConsequence["description"] === "string"
      ? previousConsequence["description"]
      : null;
  const rewardEvent = [...game.history]
    .reverse()
    .find((event) => event.event_type === "rewards_granted");
  const rewardNotices = Array.isArray(rewardEvent?.payload["rewards"])
    ? rewardEvent.payload["rewards"].flatMap((rawReward): string[] => {
        if (typeof rawReward !== "object" || rawReward === null || Array.isArray(rawReward))
          return [];
        const reward = rawReward as Record<string, unknown>;
        if (
          typeof reward["character_name"] !== "string" ||
          typeof reward["xp"] !== "number" ||
          typeof reward["gold"] !== "number"
        ) {
          return [];
        }
        const items = Array.isArray(reward["items"])
          ? reward["items"].flatMap((rawItem): string[] => {
              if (typeof rawItem !== "object" || rawItem === null || Array.isArray(rawItem))
                return [];
              const item = rawItem as Record<string, unknown>;
              return typeof item["name"] === "string" && typeof item["quantity"] === "number"
                ? [`${item["name"]} ×${item["quantity"]}`]
                : [];
            })
          : [];
        return [
          `${reward["character_name"]}: +${reward["xp"]} XP${
            reward["gold"] > 0 ? ` · +${reward["gold"]} ouro` : ""
          }${items.length ? ` · ${items.join(", ")}` : ""}`,
        ];
      })
    : [];

  return (
    <section className="fantasy-card mt-8 rounded-2xl border p-5 sm:p-8">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gold">
          Partida narrativa
        </p>
        <h2 className="mt-2 font-serif text-2xl font-semibold text-foreground">
          {game.chapter.title}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{game.scene.title}</p>
      </div>

      {game.chapter.narrative && (
        <p className="mt-5 whitespace-pre-wrap text-sm leading-7 text-muted-foreground">
          {game.chapter.narrative}
        </p>
      )}
      {game.chapter.summary && (
        <p className="mt-4 text-sm leading-6 text-muted-foreground">{game.chapter.summary}</p>
      )}
      <article className="mt-5 rounded-xl border border-border bg-background/50 p-4 sm:p-5">
        <h3 className="font-serif text-xl font-semibold text-foreground">{game.scene.title}</h3>
        <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-foreground/90">
          {game.scene.narrative || "Esta cena não possui texto narrativo cadastrado."}
        </p>
      </article>

      <div className="mt-6">
        <h3 className="font-semibold text-foreground">Personagens participantes</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          {game.participants.map((participant) => (
            <span
              key={participant.user_id}
              className="rounded-full border border-border bg-background/60 px-3 py-1.5 text-xs text-muted-foreground"
            >
              {participant.character_name ?? participant.display_name}
              {participant.user_id === userId ? " (você)" : ""}
              {participant.level !== null ? ` · Nv. ${participant.level}` : ""}
            </span>
          ))}
        </div>
      </div>

      {previousChoice !== null && (
        <div className="mt-6 rounded-xl border border-magic/25 bg-magic/10 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">
            Decisão anterior
          </p>
          <p className="mt-1 text-sm font-medium text-foreground">{previousChoice}</p>
          {consequenceDescription && (
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{consequenceDescription}</p>
          )}
        </div>
      )}
      {rewardNotices.length > 0 && (
        <div
          role="status"
          aria-live="polite"
          className="mt-4 rounded-xl border border-gold/30 bg-gold/10 p-4 text-sm text-foreground"
        >
          <p className="font-semibold text-gold">Recompensas recebidas</p>
          <ul className="mt-2 space-y-1">
            {rewardNotices.map((notice, index) => (
              <li key={`${notice}-${index}`}>{notice}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-6 rounded-xl border border-primary/30 bg-primary/5 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="font-semibold text-foreground">
              {solo ? "Sua próxima escolha" : "Escolha do grupo"}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {solo
                ? "Selecione uma opção para continuar a história."
                : "Vote na opção que deve definir o próximo passo da história."}
            </p>
          </div>
          {vote && (
            <p className="rounded-full border bg-background/70 px-3 py-1 text-xs text-muted-foreground">
              {vote.status === "open"
                ? `${vote.voted_count}/${vote.eligible_count} votos`
                : vote.status === "tied"
                  ? "Empate: aguardando uma regra de desempate"
                  : vote.status === "no_votes"
                    ? "Votação encerrada sem votos"
                    : "Votação encerrada"}
              {vote.deadline_at &&
                vote.status === "open" &&
                ` · prazo ${new Date(vote.deadline_at).toLocaleString()}`}
            </p>
          )}
        </div>
        {game.scene.choices.length === 0 ? (
          <p className="mt-3 rounded-lg border border-border bg-background/50 p-4 text-sm text-muted-foreground">
            {game.status === "completed"
              ? "A progressão narrativa foi concluída."
              : "Esta cena não possui escolhas disponíveis."}
          </p>
        ) : (
          <div className="mt-3 grid gap-3">
            {game.scene.choices.map((choice) => {
              const tally = vote?.tally.find((entry) => entry.choice_id === choice.id)?.votes ?? 0;
              const selected = vote?.my_choice_id === choice.id;
              const canVote =
                vote?.status === "open" &&
                (vote.my_choice_id === null || vote.allow_vote_change || selected);
              return (
                <article
                  key={choice.id}
                  className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-background/70 p-4 ${
                    selected ? "border-primary/60 ring-1 ring-primary/20" : "border-border"
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-foreground">{choice.label}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {selected
                        ? "Sua escolha foi registrada."
                        : canVote
                          ? !solo
                            ? `${tally} ${tally === 1 ? "voto" : "votos"} · clique para votar.`
                            : "Clique para selecionar esta opção."
                          : vote?.status === "open"
                            ? "Seu voto já foi registrado; não pode ser alterado."
                            : !solo
                              ? `${tally} ${tally === 1 ? "voto" : "votos"} · votação encerrada.`
                              : "Escolha indisponível."}
                    </p>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant={selected ? "default" : "outline"}
                    disabled={!canVote || busy}
                    onClick={() => onVote(choice.id)}
                  >
                    {selected
                      ? solo
                        ? "Escolha registrada"
                        : "Voto registrado"
                      : solo
                        ? "Escolher"
                        : "Votar"}
                  </Button>
                </article>
              );
            })}
          </div>
        )}
      </div>

      <div className="mt-7">
        <h3 className="font-semibold text-foreground">Histórico da partida</h3>
        {game.history.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">Nenhum acontecimento registrado.</p>
        ) : (
          <ol className="mt-3 space-y-2">
            {game.history.map((event) => {
              const label = event.payload["choice_label"];
              const description =
                event.event_type === "decision_resolved" && typeof label === "string"
                  ? `Decisão: ${label}`
                  : event.event_type === "campaign_started"
                    ? "A campanha foi iniciada."
                    : event.event_type === "vote_tied"
                      ? "A votação terminou empatada."
                      : event.event_type === "session_completed"
                        ? "A progressão narrativa foi concluída."
                        : event.event_type === "rewards_granted"
                          ? "Recompensas concedidas aos personagens participantes."
                          : event.event_type === "vote_changed"
                            ? "Um participante alterou o voto."
                            : event.event_type === "vote_cast"
                              ? "Um participante registrou um voto."
                              : "Acontecimento registrado.";
              return (
                <li
                  key={event.sequence_number}
                  className="flex flex-wrap justify-between gap-2 rounded-lg border border-border/70 bg-background/40 px-3 py-2 text-sm"
                >
                  <span className="text-foreground">{description}</span>
                  <time className="text-xs text-muted-foreground">
                    {new Date(event.created_at).toLocaleString()}
                  </time>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </section>
  );
}

export function CampaignLobbyPage({
  user,
  campaignId,
  onLogout,
}: {
  user: AuthUser;
  campaignId: string;
  onLogout: () => Promise<void>;
}) {
  const navigate = useNavigate();
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [narrativeGame, setNarrativeGame] = useState<NarrativeGame | null>(null);
  const [activeView, setActiveView] = useState<"lobby" | "character">("lobby");
  const [characterName, setCharacterName] = useState("");
  const [soloCharacters, setSoloCharacters] = useState<SoloCharacter[]>([]);
  const [newSoloCharacterName, setNewSoloCharacterName] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [connectionError, setConnectionError] = useState("");
  const [copied, setCopied] = useState(false);
  const savedCharacterName = useRef<string | null>(null);
  const refreshPollState = useRef<NonOverlappingPollState>({
    inFlight: false,
    nextTask: null,
  });
  const presencePollState = useRef<NonOverlappingPollState>({
    inFlight: false,
    nextTask: null,
  });
  const refreshVersion = useRef(0);
  const actionInFlight = useRef(false);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const isVisible = () => document.visibilityState === "visible";
    savedCharacterName.current = null;
    async function refresh() {
      if (!active || !isVisible()) return;
      const requestVersion = refreshVersion.current;
      try {
        const currentCampaign = await getCampaign(campaignId, controller.signal);
        const currentSoloCharacters = currentCampaign.solo
          ? await listSoloCharacters(campaignId)
          : [];
        const currentGame =
          currentCampaign.status === "in_progress"
            ? await getNarrativeGame(campaignId, controller.signal)
            : null;
        if (!active || controller.signal.aborted || refreshVersion.current !== requestVersion) {
          return;
        }
        refreshVersion.current += 1;
        setCampaign(currentCampaign);
        setSoloCharacters(currentSoloCharacters);
        setNarrativeGame(currentGame);
        const currentCharacter = currentCampaign.members.find(
          (member) => member.user_id === user.id,
        )?.character_name;
        if (currentCharacter !== undefined && savedCharacterName.current !== currentCharacter) {
          savedCharacterName.current = currentCharacter;
          setCharacterName(currentCharacter ?? "");
        }
        setConnectionError("");
      } catch (requestError) {
        if (active && !controller.signal.aborted && refreshVersion.current === requestVersion) {
          setConnectionError(errorMessage(requestError, "Não foi possível atualizar o lobby."));
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    const refreshIfIdle = createNonOverlappingPoll(refresh, refreshPollState.current);
    const updatePresenceIfIdle = createNonOverlappingPoll(async () => {
      if (!active || !isVisible()) return;
      try {
        await updateCampaignPresence(campaignId, controller.signal);
      } catch (requestError: unknown) {
        if (active && !controller.signal.aborted) {
          setConnectionError(errorMessage(requestError, "A presença não pôde ser atualizada."));
        }
      }
    }, presencePollState.current);
    const refreshWhenVisible = () => {
      if (!active || !isVisible()) return;
      void refreshIfIdle();
    };
    const updatePresenceWhenVisible = () => {
      if (!active || !isVisible()) return;
      void updatePresenceIfIdle();
    };
    const onVisibilityChange = () => {
      refreshWhenVisible();
      updatePresenceWhenVisible();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    onVisibilityChange();
    const pollTimer = window.setInterval(refreshWhenVisible, 5_000);
    const presenceTimer = window.setInterval(updatePresenceWhenVisible, 15_000);
    return () => {
      active = false;
      controller.abort();
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.clearInterval(pollTimer);
      window.clearInterval(presenceTimer);
    };
  }, [campaignId, user.id]);

  async function runAction(
    action: string,
    operation: () => Promise<Campaign>,
    successMessage: string,
  ) {
    if (actionInFlight.current) return;
    actionInFlight.current = true;
    refreshVersion.current += 1;
    setBusy(action);
    setError("");
    setFeedback("");
    try {
      const updatedCampaign = await operation();
      const committedVersion = ++refreshVersion.current;
      setCampaign(updatedCampaign);
      const currentCharacter = updatedCampaign.members.find(
        (member) => member.user_id === user.id,
      )?.character_name;
      if (currentCharacter !== undefined) {
        savedCharacterName.current = currentCharacter;
        setCharacterName(currentCharacter ?? "");
      }
      const updatedGame =
        updatedCampaign.status === "in_progress" ? await getNarrativeGame(campaignId) : null;
      if (refreshVersion.current === committedVersion) setNarrativeGame(updatedGame);
      setFeedback(successMessage);
    } catch (requestError) {
      setError(errorMessage(requestError, "Não foi possível concluir a ação."));
    } finally {
      actionInFlight.current = false;
      setBusy("");
    }
  }

  async function handleLeave() {
    if (campaign === null) return;
    if (
      campaign.solo &&
      !window.confirm("Abandonar esta campanha solo? O progresso salvo será mantido.")
    ) {
      return;
    }
    if (actionInFlight.current) return;
    actionInFlight.current = true;
    refreshVersion.current += 1;
    setBusy("leave");
    setError("");
    try {
      await leaveCampaign(campaignId);
      refreshVersion.current += 1;
      await navigate({ to: "/play" });
    } catch (requestError) {
      setError(errorMessage(requestError, "Não foi possível sair da sala."));
    } finally {
      actionInFlight.current = false;
      setBusy("");
    }
  }

  async function handleCopyCode() {
    if (campaign === null) return;
    setError("");
    setFeedback("");
    try {
      await navigator.clipboard.writeText(campaign.join_code);
      setCopied(true);
      setFeedback("Código de convite copiado.");
      window.setTimeout(() => setCopied(false), 1800);
    } catch (requestError) {
      setError(errorMessage(requestError, "Não foi possível copiar o código."));
    }
  }

  async function handleStart() {
    await runAction("start", () => startCampaign(campaignId), "A campanha foi iniciada.");
  }

  async function handleVote(choiceId: string) {
    setBusy("vote");
    setError("");
    setFeedback("");
    try {
      const updatedGame = await castNarrativeVote(campaignId, choiceId);
      refreshVersion.current += 1;
      setNarrativeGame(updatedGame);
      setFeedback("Seu voto foi registrado e a votação foi atualizada.");
    } catch (requestError) {
      setError(errorMessage(requestError, "Não foi possível registrar seu voto."));
    } finally {
      setBusy("");
    }
  }

  async function handleReadyToggle() {
    if (campaign === null) return;
    const member = campaign.members.find((candidate) => candidate.user_id === user.id);
    if (member === undefined) return;
    await runAction(
      "ready",
      () => updateCampaignReady(campaignId, !member.is_ready),
      member.is_ready ? "Sua prontidão foi atualizada." : "Você marcou que está pronto.",
    );
  }

  async function handleCharacterSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runAction(
      "character",
      () => updateCampaignCharacter(campaignId, characterName),
      "Nome do personagem salvo.",
    );
  }

  async function handleSoloCharacterCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("solo-character-create");
    setError("");
    try {
      await createSoloCharacter(campaignId, newSoloCharacterName);
      setNewSoloCharacterName("");
      const [updatedCharacters, updatedCampaign] = await Promise.all([
        listSoloCharacters(campaignId),
        getCampaign(campaignId),
      ]);
      setSoloCharacters(updatedCharacters);
      setCampaign(updatedCampaign);
      setCharacterName(
        updatedCampaign.members.find((member) => member.user_id === user.id)?.character_name ?? "",
      );
    } catch (requestError) {
      setError(errorMessage(requestError, "Não foi possível criar o personagem solo."));
    } finally {
      setBusy("");
    }
  }

  async function handleSoloCharacterSelect(characterId: string) {
    setBusy("solo-character-select");
    setError("");
    try {
      await selectSoloCharacter(campaignId, characterId);
      const [updatedCharacters, updatedCampaign] = await Promise.all([
        listSoloCharacters(campaignId),
        getCampaign(campaignId),
      ]);
      setSoloCharacters(updatedCharacters);
      setCampaign(updatedCampaign);
      setCharacterName(
        updatedCampaign.members.find((member) => member.user_id === user.id)?.character_name ?? "",
      );
    } catch (requestError) {
      setError(errorMessage(requestError, "Não foi possível trocar o personagem ativo."));
    } finally {
      setBusy("");
    }
  }

  async function handleLogout() {
    setBusy("logout");
    setError("");
    try {
      await onLogout();
    } catch (requestError) {
      setError(errorMessage(requestError, "Não foi possível encerrar a sessão."));
      setBusy("");
    }
  }

  if (loading) {
    return (
      <main
        role="status"
        aria-live="polite"
        className="flex min-h-screen items-center justify-center gap-2 text-sm text-muted-foreground"
      >
        <RefreshCw className="size-4 animate-spin" />
        Carregando sala...
      </main>
    );
  }
  if (campaign === null) {
    return (
      <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center px-5">
        <p
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
        >
          {connectionError || "Esta campanha não existe ou você não participa mais dela."}
        </p>
        <Link to="/play" className="mt-4 text-sm text-primary hover:underline">
          Voltar às minhas campanhas
        </Link>
      </main>
    );
  }

  const ownMember = campaign.members.find((member) => member.user_id === user.id);
  const isWaiting = campaign.status === "waiting";

  if (activeView === "character") {
    return (
      <CharacterSheet
        campaignId={campaignId}
        onBack={() => setActiveView("lobby")}
        onCharacterRenamed={(name) => {
          savedCharacterName.current = name;
          setCharacterName(name);
          setCampaign((current) =>
            current === null
              ? current
              : {
                  ...current,
                  members: current.members.map((member) =>
                    member.user_id === user.id ? { ...member, character_name: name } : member,
                  ),
                },
          );
        }}
        onLogout={onLogout}
      />
    );
  }

  return (
    <main className="min-h-screen">
      <header className="border-b border-border/70 bg-background/80">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <nav aria-label="Navegação da campanha" className="flex flex-wrap items-center gap-2">
            <Link
              to="/play"
              className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="size-4" />
              Minhas campanhas
            </Link>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setActiveView("character")}
            >
              Minha ficha
            </Button>
          </nav>
          <Button type="button" variant="ghost" size="sm" onClick={() => void handleLogout()}>
            <LogOut className="size-4" />
            Sair
          </Button>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-5 py-8 sm:px-8 sm:py-12">
        {error && (
          <p
            role="alert"
            className="mb-5 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
          >
            {error}
          </p>
        )}
        {feedback && (
          <p
            role="status"
            aria-live="polite"
            className="mb-5 rounded-lg border border-emerald-500/25 bg-emerald-500/5 p-3 text-sm text-emerald-300"
          >
            {feedback}
          </p>
        )}
        {connectionError && (
          <p
            role="status"
            className="mb-5 rounded-lg border border-gold/25 bg-gold/5 p-3 text-sm text-gold"
          >
            {connectionError} Tentando atualizar novamente...
          </p>
        )}

        <section className="fantasy-card rounded-2xl border p-5 sm:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
                Lobby da campanha
              </p>
              <h1 className="mt-2 font-serif text-3xl font-semibold text-foreground sm:text-4xl">
                {campaign.title}
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Sala persistente · Proprietário: {campaign.owner_display_name}
              </p>
            </div>
            <CampaignStatus status={campaign.status} />
          </div>

          {campaign.description && (
            <p className="mt-5 max-w-3xl leading-7 text-muted-foreground">{campaign.description}</p>
          )}

          {!campaign.solo && (
            <div className="mt-6 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-background/60 p-4">
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-foreground">
                  Convide participantes para a sala
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Compartilhe este código com quem deve participar da campanha.
                </p>
                <p className="mt-1 break-all font-mono text-xl font-semibold tracking-[0.2em] text-gold">
                  {campaign.join_code}
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void handleCopyCode()}
                aria-live="polite"
              >
                {copied ? <Check /> : <Copy />}
                {copied ? "Copiado" : "Copiar código"}
              </Button>
            </div>
          )}

          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            {!campaign.solo && (
              <div className="rounded-xl border border-border/80 bg-background/45 p-4">
                <p className="text-xs text-muted-foreground">Participantes</p>
                <p className="mt-1 font-semibold text-foreground">
                  {campaign.participant_count} / {campaign.max_players}
                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                    · {campaign.available_slots} vagas
                  </span>
                </p>
              </div>
            )}
            <div className="rounded-xl border border-border/80 bg-background/45 p-4">
              <p className="text-xs text-muted-foreground">Mínimo para iniciar</p>
              <p className="mt-1 font-semibold text-foreground">{campaign.min_players} jogadores</p>
            </div>
            <div className="rounded-xl border border-border/80 bg-background/45 p-4">
              <p className="text-xs text-muted-foreground">Progresso salvo</p>
              <p className="mt-1 font-semibold text-foreground">
                {campaign.status === "in_progress"
                  ? "Campanha em andamento"
                  : campaign.current_chapter_id
                    ? "Capítulo iniciado"
                    : "Aguardando início"}
              </p>
            </div>
          </div>
        </section>

        {campaign.solo && campaign.is_owner && (
          <section className="fantasy-card mt-6 rounded-2xl border p-5 sm:p-7">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="font-serif text-xl font-semibold text-foreground">
                  Personagem da aventura solo
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Você é o único participante. Os personagens abaixo são alternativas; somente o
                  marcado como ativo joga. Trocas disponíveis antes de iniciar ou com a aventura
                  pausada.
                </p>
              </div>
              <span className="text-xs text-muted-foreground">{soloCharacters.length}/5</span>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {soloCharacters.map((character) => (
                <article
                  key={character.id}
                  className="rounded-xl border border-border/80 bg-background/45 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-foreground">{character.name}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Nv. {character.level} · HP {character.hp}/{character.max_hp}
                        {character.character_class ? ` · ${character.character_class}` : ""}
                      </p>
                    </div>
                    {character.active ? (
                      <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-400">
                        Ativo
                      </span>
                    ) : (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={busy !== "" || !["waiting", "paused"].includes(campaign.status)}
                        onClick={() => void handleSoloCharacterSelect(character.id)}
                      >
                        Usar personagem
                      </Button>
                    )}
                  </div>
                </article>
              ))}
            </div>
            {soloCharacters.length < 5 && ["waiting", "paused"].includes(campaign.status) && (
              <form
                onSubmit={(event) => void handleSoloCharacterCreate(event)}
                className="mt-4 flex flex-col gap-2 sm:flex-row"
              >
                <label className="sr-only" htmlFor="new-solo-character-name">
                  Nome do novo personagem
                </label>
                <Input
                  id="new-solo-character-name"
                  value={newSoloCharacterName}
                  onChange={(event) => setNewSoloCharacterName(event.target.value)}
                  placeholder="Nome do novo personagem"
                  maxLength={100}
                  required
                />
                <Button type="submit" variant="outline" disabled={busy !== ""}>
                  Criar personagem
                </Button>
              </form>
            )}
          </section>
        )}

        {narrativeGame && (
          <NarrativeGamePanel
            game={narrativeGame}
            userId={user.id}
            busy={busy === "vote"}
            onVote={(choiceId) => void handleVote(choiceId)}
            solo={campaign.solo}
          />
        )}

        {campaign.status === "in_progress" && <CombatPanel campaign={campaign} user={user} />}

        <section className="mt-8">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="font-serif text-2xl font-semibold text-foreground">Participantes</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                A presença e a prontidão de cada participante são atualizadas enquanto a sala está
                aberta.
              </p>
            </div>
            <div className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <RefreshCw className="size-3.5 animate-spin" />
              Atualização automática
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {campaign.members.map((member) => (
              <article
                key={member.user_id}
                className="fantasy-card min-w-0 rounded-xl border p-4 sm:p-5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <CircleUserRound className="size-5" />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate font-medium text-foreground">{member.display_name}</p>
                      <p className="break-all text-xs text-muted-foreground">
                        {member.role === "owner" ? "Proprietário da sala" : `@${member.username}`}
                      </p>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5 text-xs">
                    {member.is_connected ? (
                      <>
                        <Wifi className="size-3.5 text-emerald-400" />
                        <span className="text-emerald-400">Conectado</span>
                      </>
                    ) : (
                      <>
                        <WifiOff className="size-3.5 text-muted-foreground" />
                        <span className="text-muted-foreground">Desconectado</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-border/70 pt-3">
                  <div className="min-w-0">
                    <p className="text-xs text-muted-foreground">Personagem</p>
                    <p className="mt-0.5 break-all text-sm font-medium text-foreground">
                      {member.character_name ?? "Ainda não criado"}
                      {member.level !== null && (
                        <span className="ml-2 text-xs text-muted-foreground">
                          Nv. {member.level}
                        </span>
                      )}
                    </p>
                  </div>
                  <span
                    className={`rounded-full border px-2.5 py-1 text-xs ${
                      member.is_ready
                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                        : "border-border bg-background text-muted-foreground"
                    }`}
                  >
                    {member.is_ready ? "Pronto" : "Ainda não está pronto"}
                  </span>
                </div>
                {member.user_id === user.id && member.character_name !== null && (
                  <form
                    onSubmit={(event) => void handleCharacterSave(event)}
                    className="mt-4 flex flex-col gap-2 border-t border-border/70 pt-3 sm:flex-row"
                  >
                    <label className="sr-only" htmlFor="campaign-character-name">
                      Nome do seu personagem
                    </label>
                    <Input
                      id="campaign-character-name"
                      value={characterName}
                      onChange={(event) => setCharacterName(event.target.value)}
                      maxLength={100}
                      required
                    />
                    <Button
                      type="submit"
                      variant="outline"
                      size="sm"
                      disabled={busy === "character"}
                    >
                      {busy === "character" ? "Salvando..." : "Salvar personagem"}
                    </Button>
                  </form>
                )}
              </article>
            ))}
          </div>
        </section>

        <section className="fantasy-card mt-8 flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4 sm:p-5">
          <div>
            <p className="font-medium text-foreground">Preparação da sua conta</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Marque sua prontidão para informar o grupo. O proprietário acompanha os participantes
              e inicia a campanha conforme as regras da sala.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {isWaiting && (
              <Button
                type="button"
                variant="outline"
                onClick={() => void handleReadyToggle()}
                disabled={busy !== ""}
              >
                {ownMember?.is_ready ? "Ainda estou preparando" : "Marcar como pronto"}
              </Button>
            )}
            {campaign.is_owner && isWaiting && (
              <Button type="button" onClick={() => void handleStart()} disabled={busy !== ""}>
                <Play />
                {busy === "start" ? "Iniciando..." : "Iniciar campanha"}
              </Button>
            )}
            {campaign.solo && campaign.is_owner && campaign.status === "in_progress" && (
              <Button
                type="button"
                variant="outline"
                onClick={() =>
                  void runAction("pause", () => pauseCampaign(campaignId), "Campanha solo pausada.")
                }
                disabled={busy !== ""}
              >
                Pausar aventura
              </Button>
            )}
            {campaign.solo && campaign.is_owner && campaign.status === "paused" && (
              <Button
                type="button"
                onClick={() =>
                  void runAction(
                    "resume",
                    () => resumeCampaign(campaignId),
                    "Campanha solo retomada.",
                  )
                }
                disabled={busy !== ""}
              >
                Continuar aventura
              </Button>
            )}
            <Button
              type="button"
              variant="outline"
              onClick={() => void handleLeave()}
              disabled={busy !== ""}
            >
              <DoorOpen />
              Sair da sala
            </Button>
          </div>
        </section>

        <p className="mt-5 flex items-center gap-2 text-xs leading-5 text-muted-foreground">
          <Shield className="size-3.5 shrink-0" />O proprietário administra a sala, mas não recebe
          poderes de mestre no jogo. O servidor valida entrada, permissões e início da campanha.
        </p>
      </div>
    </main>
  );
}
