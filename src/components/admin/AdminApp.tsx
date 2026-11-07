import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Coins,
  FlaskConical,
  Gem,
  Image,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  ScrollText,
  Settings,
  Shield,
  Skull,
  Sparkles,
  Swords,
  Users,
  Bell,
  WandSparkles,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { ConfirmDialog } from "@/components/common/ui-bits";
import { Toaster } from "@/components/ui/sonner";
import { useCollection } from "@/hooks/use-collection";
import { dataService } from "@/services/dataService";
import { useQueryClient } from "@tanstack/react-query";
import { adminContentRequest } from "@/lib/admin-content-api";
import { CampaignsPage, EconomyPage, PlayersAndCharactersPage } from "./ManagementPages";
import { StoryPage } from "./StoryPage";
import { MissionManagementPage } from "./MissionManagementPage";
import { CombatBalancePage } from "./CombatBalancePage";
import { CreationsPage } from "./CreationsPage";

type PageId =
  | "overview"
  | "campaigns"
  | "story"
  | "missions"
  | "players"
  | "creations"
  | "combat-balance"
  | "economy"
  | "settings";

const navigation: { id: PageId; label: string; icon: typeof LayoutDashboard }[] = [
  { id: "overview", label: "Visão geral", icon: LayoutDashboard },
  { id: "campaigns", label: "Campanhas", icon: ScrollText },
  { id: "story", label: "História e capítulos", icon: BookOpen },
  { id: "missions", label: "Missões", icon: ScrollText },
  { id: "players", label: "Jogadores", icon: Users },
  { id: "creations", label: "Criações", icon: WandSparkles },
  { id: "combat-balance", label: "Balanceamento", icon: Activity },
  { id: "economy", label: "Economia e recompensas", icon: Coins },
  { id: "settings", label: "Configurações", icon: Settings },
];

const PAGE_TITLES = Object.fromEntries(
  navigation.map((entry) => [entry.id, entry.label]),
) as Record<PageId, string>;

function initialPage(): PageId {
  if (typeof window === "undefined") return "overview";
  const candidate = new URLSearchParams(window.location.search).get("page");
  if (
    candidate &&
    ["characters", "creatures", "skills", "items", "assets", "animations"].includes(candidate)
  ) {
    return "creations";
  }
  return navigation.some((entry) => entry.id === candidate) ? (candidate as PageId) : "overview";
}

function NavItems({
  page,
  collapsed,
  onNavigate,
}: {
  page: PageId;
  collapsed: boolean;
  onNavigate: (id: PageId) => void;
}) {
  return (
    <nav aria-label="Navegação principal" className="space-y-1">
      {navigation.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          title={collapsed ? label : undefined}
          aria-current={page === id ? "page" : undefined}
          onClick={() => onNavigate(id)}
          className={`group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-all ${
            page === id
              ? "bg-primary/15 text-primary shadow-sm shadow-primary/5"
              : "text-sidebar-foreground/65 hover:bg-sidebar-accent hover:text-sidebar-foreground"
          } ${collapsed ? "justify-center px-2" : ""}`}
        >
          <Icon className={`h-[18px] w-[18px] shrink-0 ${page === id ? "text-primary" : ""}`} />
          {!collapsed && <span className="truncate">{label}</span>}
          {!collapsed && page === id && (
            <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary" />
          )}
        </button>
      ))}
    </nav>
  );
}

function Sidebar({
  page,
  collapsed,
  projectName,
  onNavigate,
  onToggle,
}: {
  page: PageId;
  collapsed: boolean;
  projectName: string;
  onNavigate: (id: PageId) => void;
  onToggle: () => void;
}) {
  return (
    <aside
      className={`hidden h-screen shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200 lg:sticky lg:top-0 lg:flex ${collapsed ? "w-[76px]" : "w-[258px]"}`}
    >
      <div
        className={`flex h-[76px] items-center border-b border-sidebar-border ${collapsed ? "justify-center px-2" : "gap-3 px-5"}`}
      >
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/30 bg-primary/10 text-primary">
          <Swords className="h-5 w-5" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate font-display text-base text-sidebar-foreground">{projectName}</p>
            <p className="mt-0.5 text-[10px] uppercase tracking-[0.2em] text-sidebar-foreground/65">
              Painel do mestre
            </p>
          </div>
        )}
      </div>
      <div className={`px-3 pb-3 pt-6 ${collapsed ? "px-2" : ""}`}>
        {!collapsed && (
          <p className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-sidebar-foreground/65">
            Gestão do mundo
          </p>
        )}
        <NavItems page={page} collapsed={collapsed} onNavigate={onNavigate} />
      </div>
      <div className="mt-auto p-3">
        {!collapsed && (
          <div className="rounded-xl border border-gold/20 bg-gold/5 p-3">
            <div className="flex items-center gap-2 text-gold">
              <FlaskConical className="h-4 w-4" />
              <span className="text-xs font-medium">Dados mistos</span>
            </div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-sidebar-foreground/65">
              Campanhas, contas, personagens e catálogos usam o servidor. Eventos de atividade e
              preferências locais são demonstração.
            </p>
          </div>
        )}
        <Button
          variant="ghost"
          size="sm"
          className={`mt-2 w-full text-sidebar-foreground/65 hover:text-sidebar-foreground ${collapsed ? "px-0" : "justify-start"}`}
          onClick={onToggle}
          aria-label={collapsed ? "Expandir menu lateral" : "Recolher menu lateral"}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <>
              <ChevronLeft className="h-4 w-4" />
              <span>Recolher menu</span>
            </>
          )}
        </Button>
      </div>
    </aside>
  );
}

function StatCard({
  title,
  value,
  caption,
  icon: Icon,
  tone,
}: {
  title: string;
  value: number;
  caption: string;
  icon: typeof Users;
  tone: string;
}) {
  return (
    <Card className="panel-card">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.13em] text-muted-foreground">
              {title}
            </p>
            <p className="mt-3 font-display text-3xl text-foreground">{value}</p>
            <p className="mt-1 text-xs text-muted-foreground">{caption}</p>
          </div>
          <div className={`rounded-xl border p-2.5 ${tone}`}>
            <Icon className="h-[18px] w-[18px]" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function Overview({ onNavigate }: { onNavigate: (id: PageId) => void }) {
  const { data: campaigns = [] } = useCollection("campaigns");
  const { data: players = [] } = useCollection("players");
  const { data: characters = [] } = useCollection("characters");
  const { data: chapters = [] } = useCollection("chapters");
  const { data: monsters = [] } = useCollection("monsters");
  const { data: events = [] } = useCollection("events");
  const activeCampaigns = campaigns.filter((campaign) => campaign.status === "em_andamento");
  const latestEvents = [...events].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 5);
  const eventIcons: Record<string, typeof Activity> = {
    campanha: ScrollText,
    capitulo: BookOpen,
    jogador: Users,
    criatura: Skull,
    item: Gem,
  };
  const stats = [
    {
      title: "Campanhas",
      value: campaigns.length,
      caption: `${activeCampaigns.length} em andamento`,
      icon: ScrollText,
      tone: "border-primary/20 bg-primary/10 text-primary",
    },
    {
      title: "Jogadores",
      value: players.length,
      caption: `${players.filter((player) => player.status === "ativo").length} ativos`,
      icon: Users,
      tone: "border-sky-400/20 bg-sky-400/10 text-sky-300",
    },
    {
      title: "Personagens",
      value: characters.length,
      caption: "Fichas cadastradas",
      icon: Shield,
      tone: "border-emerald-400/20 bg-emerald-400/10 text-emerald-300",
    },
    {
      title: "Capítulos",
      value: chapters.length,
      caption: `${chapters.filter((chapter) => chapter.status === "publicado").length} publicados`,
      icon: BookOpen,
      tone: "border-gold/20 bg-gold/10 text-gold",
    },
    {
      title: "Criaturas",
      value: monsters.length,
      caption: "No bestiário",
      icon: Skull,
      tone: "border-rose-400/20 bg-rose-400/10 text-rose-300",
    },
  ];
  return (
    <div className="space-y-7">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-[0.2em] text-primary">
            Painel de controle
          </p>
          <h1 className="font-display text-3xl text-foreground sm:text-4xl">Visão geral</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Acompanhe o estado das suas campanhas e do mundo.
          </p>
        </div>
        <Badge
          variant="outline"
          className="w-fit gap-1.5 border-gold/30 bg-gold/5 px-2.5 py-1 text-gold"
        >
          <FlaskConical className="h-3.5 w-3.5" /> Conteúdo híbrido
        </Badge>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {stats.map((stat) => (
          <StatCard key={stat.title} {...stat} />
        ))}
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.4fr_0.9fr]">
        <Card className="panel-card">
          <CardHeader className="flex-row items-start justify-between space-y-0">
            <div>
              <CardTitle className="font-display text-xl">Campanhas ativas</CardTitle>
              <CardDescription className="mt-1">Jornadas em andamento no momento.</CardDescription>
            </div>
            <Button variant="ghost" size="sm" onClick={() => onNavigate("campaigns")}>
              Ver todas <ChevronRight className="h-4 w-4" />
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {activeCampaigns.length ? (
              activeCampaigns.map((campaign) => {
                const chapter = chapters.find((item) => item.id === campaign.startChapterId);
                return (
                  <button
                    key={campaign.id}
                    onClick={() => onNavigate("campaigns")}
                    className="group flex w-full items-center justify-between gap-4 rounded-lg border border-border/70 bg-background/45 p-4 text-left transition-colors hover:border-primary/30 hover:bg-primary/5"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium text-foreground group-hover:text-primary">
                        {campaign.title}
                      </p>
                      <p className="mt-1 truncate text-xs text-muted-foreground">
                        {chapter?.title ?? "Capítulo não definido"} · {campaign.playerIds.length}{" "}
                        jogadores
                      </p>
                    </div>
                    <Badge
                      variant="outline"
                      className="shrink-0 border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                    >
                      Em andamento
                    </Badge>
                  </button>
                );
              })
            ) : (
              <p className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                Nenhuma campanha em andamento. Crie ou atualize uma campanha para começar.
              </p>
            )}
          </CardContent>
        </Card>

        <Card className="panel-card">
          <CardHeader>
            <CardTitle className="font-display text-xl">Atividade recente</CardTitle>
            <CardDescription>Últimas atualizações registradas na demonstração.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {latestEvents.length ? (
              latestEvents.map((event) => {
                const Icon = eventIcons[event.kind] ?? Activity;
                return (
                  <div key={event.id} className="flex gap-3">
                    <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-background text-muted-foreground">
                      <Icon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm leading-relaxed text-foreground/90">{event.text}</p>
                      <p className="mt-1 text-[11px] text-muted-foreground">{event.date}</p>
                    </div>
                  </div>
                );
              })
            ) : (
              <p className="text-sm text-muted-foreground">Nenhuma atividade registrada.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
        <Card className="panel-card">
          <CardHeader>
            <CardTitle className="font-display text-xl">Atalhos administrativos</CardTitle>
            <CardDescription>Acesse rapidamente as ferramentas do mestre.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-2">
            {navigation
              .filter((entry) => entry.id !== "overview" && entry.id !== "settings")
              .map(({ id, label, icon: Icon }) => (
                <Button
                  key={id}
                  variant="outline"
                  className="h-auto min-h-11 justify-start whitespace-normal px-3 py-2.5 text-left text-xs"
                  onClick={() => onNavigate(id)}
                >
                  <Icon className="h-4 w-4 shrink-0 text-primary" />
                  {label}
                </Button>
              ))}
          </CardContent>
        </Card>
        <Card className="panel-card world-state-card">
          <CardHeader className="relative z-10">
            <div className="flex items-center gap-2 text-gold">
              <Moon className="h-4 w-4" />
              <span className="text-xs font-semibold uppercase tracking-[0.18em]">
                Estado do mundo
              </span>
            </div>
            <CardTitle className="relative z-10 mt-2 font-display text-2xl">
              O reino está em movimento
            </CardTitle>
            <CardDescription className="relative z-10 max-w-xl text-sm leading-relaxed">
              {activeCampaigns[0]?.worldState ??
                "Defina o estado do mundo nas campanhas para registrar ameaças, mudanças e eventos importantes."}
            </CardDescription>
          </CardHeader>
          <CardContent className="relative z-10 flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
              {campaigns.length} campanhas registradas
            </Badge>
            <Badge variant="outline" className="border-gold/30 bg-gold/5 text-gold">
              {chapters.filter((chapter) => chapter.status === "publicado").length} capítulos
              publicados
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto"
              onClick={() => onNavigate("campaigns")}
            >
              Atualizar mundo <ChevronRight className="h-4 w-4" />
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function UniverseSettingsCard() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["admin-content", "universe-settings"],
    queryFn: () => adminContentRequest("/api/admin/content/settings/universe"),
  });
  const [values, setValues] = useState({ name: "", overview: "", narrativeRules: "" });

  useEffect(() => {
    if (typeof query.data !== "object" || query.data === null || Array.isArray(query.data)) return;
    const data = query.data as Record<string, unknown>;
    setValues({
      name: typeof data["name"] === "string" ? data["name"] : "",
      overview: typeof data["overview"] === "string" ? data["overview"] : "",
      narrativeRules: typeof data["narrative_rules"] === "string" ? data["narrative_rules"] : "",
    });
  }, [query.data]);

  const save = useMutation({
    mutationFn: () =>
      adminContentRequest("/api/admin/content/settings/universe", "PUT", {
        value: {
          name: values.name.trim(),
          overview: values.overview.trim(),
          narrative_rules: values.narrativeRules.trim(),
        },
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-content", "universe-settings"] });
      toast.success("Configurações do universo salvas no servidor.");
    },
    onError: (error) =>
      toast.error("Não foi possível salvar as configurações do universo.", {
        description: error instanceof Error ? error.message : String(error),
      }),
  });

  return (
    <Card className="panel-card">
      <CardHeader>
        <CardTitle className="font-display text-xl">Configurações do universo</CardTitle>
        <CardDescription>
          Metadados narrativos oficiais salvos no banco e disponíveis para integração futura do
          jogo.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <p className="text-sm text-muted-foreground">Carregando configurações do servidor…</p>
        ) : query.error ? (
          <p role="alert" className="text-sm text-destructive">
            Não foi possível carregar as configurações. {query.error.message}
          </p>
        ) : (
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              if (!values.name.trim()) {
                toast.error("Informe o nome do universo.");
                return;
              }
              save.mutate();
            }}
          >
            <label className="block space-y-2 text-sm font-medium">
              Nome do universo
              <Input
                value={values.name}
                onChange={(event) => setValues((old) => ({ ...old, name: event.target.value }))}
                maxLength={120}
              />
            </label>
            <label className="block space-y-2 text-sm font-medium">
              Visão geral
              <Textarea
                rows={3}
                value={values.overview}
                onChange={(event) => setValues((old) => ({ ...old, overview: event.target.value }))}
              />
            </label>
            <label className="block space-y-2 text-sm font-medium">
              Diretrizes narrativas
              <Textarea
                rows={3}
                value={values.narrativeRules}
                onChange={(event) =>
                  setValues((old) => ({ ...old, narrativeRules: event.target.value }))
                }
              />
            </label>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? "Salvando..." : "Salvar no servidor"}
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  );
}

function SettingsPage({
  collapsed,
  onToggleSidebar,
  projectName,
  onProjectNameChange,
  onSettingsSaved,
}: {
  collapsed: boolean;
  onToggleSidebar: () => void;
  projectName: string;
  onProjectNameChange: (name: string) => void;
  onSettingsSaved: (compact: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [density, setDensity] = useState(() =>
    typeof window === "undefined"
      ? "confortavel"
      : (window.localStorage.getItem("rpg-admin-density") ?? "confortavel"),
  );
  const [minimumPlayers, setMinimumPlayers] = useState(() =>
    typeof window === "undefined"
      ? "3"
      : (window.localStorage.getItem("rpg-admin-campaign-minimum-players") ?? "3"),
  );
  const [maximumPlayers, setMaximumPlayers] = useState(() =>
    typeof window === "undefined"
      ? "5"
      : (window.localStorage.getItem("rpg-admin-campaign-maximum-players") ?? "7"),
  );
  const [saved, setSaved] = useState(false);

  function saveSettings() {
    const name = projectName.trim();
    if (!name) {
      toast.error("Informe um nome para o projeto.");
      return;
    }
    if (Number(minimumPlayers) > Number(maximumPlayers)) {
      toast.error("O mínimo de jogadores não pode superar o máximo.");
      return;
    }
    window.localStorage.setItem("rpg-admin-project-name", name);
    window.localStorage.setItem("rpg-admin-density", density);
    window.localStorage.setItem("rpg-admin-campaign-minimum-players", minimumPlayers);
    window.localStorage.setItem("rpg-admin-campaign-maximum-players", maximumPlayers);
    onProjectNameChange(name);
    onSettingsSaved(density === "compacta");
    setSaved(true);
    toast.success("Preferências salvas neste navegador.");
  }

  async function resetDemo() {
    try {
      await dataService.reset();
      await Promise.all(
        (["events"] as const).map((collection) =>
          queryClient.invalidateQueries({ queryKey: ["admin-content", collection] }),
        ),
      );
      toast.success("Dados de demonstração restaurados.");
    } catch (error) {
      toast.error("Não foi possível restaurar os dados de demonstração.", {
        description: String(error),
      });
    }
  }

  return (
    <div>
      <div className="mb-6">
        <p className="mb-2 text-xs font-medium uppercase tracking-[0.2em] text-primary">
          Preferências
        </p>
        <h1 className="font-display text-3xl">Configurações</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Ajuste a experiência local do painel e restaure somente os eventos de demonstração.
        </p>
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <Card className="panel-card">
          <CardHeader>
            <CardTitle className="font-display text-xl">Painel</CardTitle>
            <CardDescription>Identidade e apresentação da interface.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <label className="block space-y-2 text-sm font-medium" htmlFor="project-name">
              Nome do projeto
              <Input
                id="project-name"
                value={projectName}
                onChange={(event) => {
                  onProjectNameChange(event.target.value);
                  setSaved(false);
                }}
                maxLength={60}
              />
            </label>
            <div>
              <p className="mb-2 text-sm font-medium">Densidade da interface</p>
              <Tabs value={density} onValueChange={setDensity}>
                <TabsList>
                  <TabsTrigger value="confortavel">Confortável</TabsTrigger>
                  <TabsTrigger value="compacta">Compacta</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-2 text-sm font-medium">
                Mínimo padrão de jogadores
                <Select value={minimumPlayers} onValueChange={setMinimumPlayers}>
                  <SelectTrigger aria-label="Mínimo padrão de jogadores">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {["3", "4", "5"].map((value) => (
                      <SelectItem key={value} value={value}>
                        {value} jogadores
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </label>
              <label className="space-y-2 text-sm font-medium">
                Máximo padrão de jogadores
                <Select value={maximumPlayers} onValueChange={setMaximumPlayers}>
                  <SelectTrigger aria-label="Máximo padrão de jogadores">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {["3", "4", "5", "6", "7"].map((value) => (
                      <SelectItem key={value} value={value}>
                        {value} jogadores
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </label>
            </div>
            <div className="flex items-center justify-between gap-4 rounded-lg border border-border p-3">
              <div>
                <p className="text-sm font-medium">Menu lateral</p>
                <p className="text-xs text-muted-foreground">
                  {collapsed ? "Recolhido" : "Expandido"}
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={onToggleSidebar}>
                Alternar menu
              </Button>
            </div>
            <Button onClick={saveSettings}>
              {saved ? "Preferências salvas" : "Salvar preferências"}
            </Button>
          </CardContent>
        </Card>
        <Card className="panel-card">
          <CardHeader>
            <CardTitle className="font-display text-xl">
              Preferências e dados demonstrativos
            </CardTitle>
            <CardDescription>Estas preferências controlam somente esta interface.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg border border-gold/20 bg-gold/5 p-4">
              <div className="flex items-center gap-2 text-gold">
                <FlaskConical className="h-4 w-4" />
                <span className="text-sm font-medium">Modo híbrido: servidor e demonstração</span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                Campanhas, contas, personagens e conteúdo oficial são consultados no servidor.
                Somente eventos de demonstração e preferências visuais ficam locais.
              </p>
            </div>
            <ConfirmDialog
              title="Restaurar dados de demonstração?"
              description="Somente os eventos de atividade demonstrativos locais serão restaurados. Dados oficiais e campanhas no servidor não serão alterados."
              confirmLabel="Restaurar dados"
              onConfirm={() => {
                void resetDemo();
              }}
              trigger={<Button variant="destructive">Restaurar dados iniciais</Button>}
            />
          </CardContent>
        </Card>
        <UniverseSettingsCard />
      </div>
    </div>
  );
}

function CurrentPage({
  page,
  collapsed,
  onToggleSidebar,
  onNavigate,
  projectName,
  onProjectNameChange,
  onSettingsSaved,
}: {
  page: PageId;
  collapsed: boolean;
  onToggleSidebar: () => void;
  onNavigate: (id: PageId) => void;
  projectName: string;
  onProjectNameChange: (name: string) => void;
  onSettingsSaved: (compact: boolean) => void;
}) {
  switch (page) {
    case "overview":
      return <Overview onNavigate={onNavigate} />;
    case "campaigns":
      return <CampaignsPage />;
    case "story":
      return <StoryPage />;
    case "missions":
      return <MissionManagementPage />;
    case "players":
      return <PlayersAndCharactersPage key="players" initialTab="players" />;
    case "creations":
      return <CreationsPage />;
    case "combat-balance":
      return <CombatBalancePage />;
    case "economy":
      return <EconomyPage />;
    case "settings":
      return (
        <SettingsPage
          collapsed={collapsed}
          onToggleSidebar={onToggleSidebar}
          projectName={projectName}
          onProjectNameChange={onProjectNameChange}
          onSettingsSaved={onSettingsSaved}
        />
      );
  }
}

export function AdminApp({ onLogout }: { onLogout: () => Promise<void> }) {
  const [page, setPage] = useState<PageId>(initialPage);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [projectName, setProjectName] = useState("Crônicas do Reino");
  const [compact, setCompact] = useState(false);
  const onToggleSidebar = () => setCollapsed((value) => !value);

  useEffect(() => {
    setProjectName(window.localStorage.getItem("rpg-admin-project-name") ?? "Crônicas do Reino");
    setCompact(window.localStorage.getItem("rpg-admin-density") === "compacta");
  }, []);

  function navigate(id: PageId) {
    setPage(id);
    setMobileMenuOpen(false);
    const url = new URL(window.location.href);
    if (id === "overview") url.searchParams.delete("page");
    else url.searchParams.set("page", id);
    window.history.pushState(null, "", url);
  }

  useEffect(() => {
    const onPopState = () => setPage(initialPage());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    document.title = `${PAGE_TITLES[page]} · ${projectName}`;
  }, [page, projectName]);

  const pageContent: ReactNode = (
    <CurrentPage
      page={page}
      collapsed={collapsed}
      onToggleSidebar={onToggleSidebar}
      onNavigate={navigate}
      projectName={projectName}
      onProjectNameChange={setProjectName}
      onSettingsSaved={setCompact}
    />
  );

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="flex min-h-screen">
        <Sidebar
          page={page}
          collapsed={collapsed}
          projectName={projectName}
          onNavigate={navigate}
          onToggle={onToggleSidebar}
        />
        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-30 flex h-[68px] items-center justify-between border-b border-border/80 bg-background/90 px-4 backdrop-blur-xl sm:px-6 lg:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden"
                aria-label="Abrir menu de navegação"
                onClick={() => setMobileMenuOpen(true)}
              >
                <Menu className="h-5 w-5" />
              </Button>
              <div className="hidden h-8 w-8 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary sm:flex lg:hidden">
                <Swords className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{PAGE_TITLES[page]}</p>
                <p className="hidden text-[11px] text-muted-foreground sm:block">
                  {projectName} <span className="px-1 text-border">/</span> Painel do mestre
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 sm:gap-3">
              <Button
                variant="ghost"
                size="icon"
                className="relative"
                aria-label="Notificações"
                onClick={() =>
                  toast.info("Você está em dia.", {
                    description: "Não há novas notificações na demonstração.",
                  })
                }
              >
                <Bell className="h-[18px] w-[18px]" />
                <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-gold" />
              </Button>
              <Badge
                variant="outline"
                className="hidden gap-1 border-gold/30 bg-gold/5 text-[10px] text-gold sm:inline-flex"
              >
                <FlaskConical className="h-3 w-3" />
                HÍBRIDO
              </Badge>
              <Button
                variant="ghost"
                size="sm"
                className="gap-1.5 text-muted-foreground hover:text-foreground"
                aria-label="Sair da administração"
                onClick={() =>
                  void onLogout().catch((error: unknown) =>
                    toast.error("Não foi possível encerrar a sessão.", {
                      description: error instanceof Error ? error.message : String(error),
                    }),
                  )
                }
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">Sair</span>
              </Button>
              <div className="flex items-center gap-2 border-l border-border pl-3">
                <div className="hidden text-right sm:block">
                  <p className="text-xs font-medium">Mestre da campanha</p>
                  <p className="text-[10px] text-muted-foreground">Administrador</p>
                </div>
                <div className="flex h-8 w-8 items-center justify-center rounded-full border border-primary/30 bg-primary/15 text-xs font-semibold text-primary">
                  DM
                </div>
              </div>
            </div>
          </header>
          <main
            className={`mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6 sm:py-8 lg:px-8 ${compact ? "density-compact" : ""}`}
          >
            {pageContent}
            <footer className="mt-10 flex flex-col gap-2 border-t border-border/70 py-5 text-[11px] text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
              <span>
                {projectName} <span className="text-border">·</span> Painel administrativo
              </span>
              <span className="inline-flex items-center gap-1.5">
                <FlaskConical className="h-3 w-3 text-gold" />
                Conteúdo oficial no servidor · eventos e preferências em demonstração
              </span>
            </footer>
          </main>
        </div>
      </div>

      <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
        <SheetContent
          side="left"
          className="w-[290px] border-sidebar-border bg-sidebar p-0 text-sidebar-foreground"
        >
          <SheetTitle className="sr-only">Navegação principal</SheetTitle>
          <div className="flex h-[76px] items-center gap-3 border-b border-sidebar-border px-5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/30 bg-primary/10 text-primary">
              <Swords className="h-5 w-5" />
            </div>
            <div>
              <p className="font-display text-base">{projectName}</p>
              <p className="mt-0.5 text-[10px] uppercase tracking-[0.2em] text-sidebar-foreground/65">
                Painel do mestre
              </p>
            </div>
          </div>
          <div className="px-3 pb-3 pt-6">
            <p className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-sidebar-foreground/65">
              Gestão do mundo
            </p>
            <NavItems page={page} collapsed={false} onNavigate={navigate} />
          </div>
          <div className="mx-4 mt-4 rounded-xl border border-gold/20 bg-gold/5 p-3">
            <div className="flex items-center gap-2 text-gold">
              <FlaskConical className="h-4 w-4" />
              <span className="text-xs font-medium">Conteúdo híbrido</span>
            </div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-sidebar-foreground/65">
              Conteúdo oficial no servidor; eventos e preferências são demonstração local.
            </p>
          </div>
        </SheetContent>
      </Sheet>
      <Toaster position="bottom-right" />
    </div>
  );
}
