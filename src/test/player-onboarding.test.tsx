import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { navigateMock } = vi.hoisted(() => ({
  navigateMock: vi.fn(),
}));

vi.mock("@tanstack/react-router", async () => {
  const React = await import("react");
  return {
    Link: ({
      children,
      to,
      ...props
    }: AnchorHTMLAttributes<HTMLAnchorElement> & {
      to: string;
    }) => React.createElement("a", { ...props, href: to }, children),
    useNavigate: () => navigateMock,
  };
});

vi.mock("../lib/auth-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/auth-api")>();
  return {
    ...actual,
    loginAdmin: vi.fn(),
    loginPlayer: vi.fn(),
    registerPlayer: vi.fn(),
    listCampaigns: vi.fn(),
    createCampaign: vi.fn(),
    joinCampaign: vi.fn(),
    getCampaign: vi.fn(),
    getCampaignCharacterSheet: vi.fn(),
    getCampaignQuests: vi.fn(),
    acceptCampaignQuest: vi.fn(),
    getNarrativeGame: vi.fn(),
    leaveCampaign: vi.fn(),
    startCampaign: vi.fn(),
    updateCampaignCharacter: vi.fn(),
    updateCampaignPresence: vi.fn(),
    updateCampaignReady: vi.fn(),
    castNarrativeVote: vi.fn(),
  };
});

import { CampaignsHomePage, CampaignLobbyPage } from "../components/player/CampaignPages";
import { CharacterSheet } from "../components/player/CharacterSheet";
import { AdminLoginPage } from "../components/admin/AdminLoginPage";
import { EntityFormDialog } from "../components/common/EntityForm";
import { AccessPlaceholder, LandingPage } from "../components/player/PlayerPages";
import {
  createCampaign,
  getCampaign,
  getCampaignCharacterSheet,
  getCampaignQuests,
  acceptCampaignQuest,
  getNarrativeGame,
  joinCampaign,
  loginAdmin,
  listCampaigns,
  loginPlayer,
  registerPlayer,
  updateCampaignReady,
  updateCampaignCharacter,
  updateCampaignPresence,
  type AuthUser,
  type Campaign,
  type CharacterSheet as CharacterSheetData,
  type NarrativeGame,
} from "../lib/auth-api";

const user: AuthUser = {
  id: "player-1",
  username: "aventureiro",
  display_name: "Aventureiro",
};

const campaign: Campaign = {
  id: "campaign-1",
  title: "Campanha de teste",
  description: "",
  join_code: "0123456789ABCDEF0123456789ABCDEF",
  status: "waiting",
  owner_id: user.id,
  owner_display_name: user.display_name,
  min_players: 3,
  max_players: 5,
  participant_count: 1,
  available_slots: 4,
  current_chapter_id: null,
  current_node_id: null,
  last_activity_at: "2026-10-29T21:00:00Z",
  membership_status: "active",
  is_owner: true,
  solo: false,
  members: [
    {
      user_id: user.id,
      username: user.username,
      display_name: user.display_name,
      role: "owner",
      is_ready: false,
      is_connected: true,
      character_id: "character-1",
      character_name: "Personagem de teste",
      level: 1,
      hp: 10,
      max_hp: 10,
      mana: 0,
      max_mana: 0,
    },
  ],
};

const characterSheet: CharacterSheetData = {
  name: "Personagem de teste",
  description: "Descrição de teste.",
  character_class: "Sentinela",
  ancestry: "Humano",
  level: 2,
  xp: 120,
  xp_to_next_level: 200,
  xp_progress_percent: 60,
  attribute_points: 0,
  gold: 15,
  hp: 18,
  max_hp: 20,
  mana: 4,
  max_mana: 8,
  attributes: { forca: 8 },
  inventory: [],
  skills: [],
  quests: [],
  progression_history: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  navigateMock.mockResolvedValue(undefined);
  vi.mocked(loginAdmin).mockResolvedValue(user);
  vi.mocked(loginPlayer).mockResolvedValue(user);
  vi.mocked(registerPlayer).mockResolvedValue(user);
  vi.mocked(listCampaigns).mockResolvedValue([]);
  vi.mocked(createCampaign).mockResolvedValue(campaign);
  vi.mocked(joinCampaign).mockResolvedValue(campaign);
  vi.mocked(getCampaign).mockResolvedValue(campaign);
  vi.mocked(getCampaignCharacterSheet).mockResolvedValue(characterSheet);
  vi.mocked(getCampaignQuests).mockResolvedValue([]);
  vi.mocked(acceptCampaignQuest).mockResolvedValue(undefined);
  vi.mocked(updateCampaignCharacter).mockResolvedValue(campaign);
  vi.mocked(updateCampaignReady).mockResolvedValue({
    ...campaign,
    members: [{ ...campaign.members[0]!, is_ready: true }],
  });
  vi.mocked(updateCampaignPresence).mockResolvedValue(undefined);
});

afterEach(() => {
  vi.useRealTimers();
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value: "visible",
  });
});

describe("player onboarding", () => {
  it("explains the multiplayer adventure and links to account and campaign entry", () => {
    render(<LandingPage />);

    expect(screen.getByText("RPG multiplayer de fantasia medieval")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sua aventura começa com o grupo" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Criar minha conta" })).toHaveAttribute(
      "href",
      "/register",
    );
    expect(screen.getByRole("link", { name: "Entrar" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("link", { name: "Acessar campanhas" })).toHaveAttribute(
      "href",
      "/play",
    );
  });

  it("shows distinct registration and login guidance without blocking legacy passwords", () => {
    const { rerender } = render(<AccessPlaceholder mode="register" />);

    expect(screen.getByRole("heading", { name: "Criar conta de jogador" })).toBeVisible();
    expect(document.getElementById("player-password")).toHaveAttribute("minLength", "12");

    rerender(<AccessPlaceholder mode="login" />);

    expect(screen.getByRole("heading", { name: "Entrar" })).toBeVisible();
    expect(document.getElementById("player-password")).not.toHaveAttribute("minLength");
    expect(screen.getByText(/Contas existentes continuam podendo entrar/)).toBeInTheDocument();
  });

  it("submits a valid new account using the existing authentication API", async () => {
    render(<AccessPlaceholder mode="register" />);
    fireEvent.change(screen.getByLabelText(/Nome de usuário/), {
      target: { value: "novo_jogador" },
    });
    fireEvent.change(document.getElementById("player-password")!, {
      target: { value: "senha-com-12+" },
    });
    fireEvent.change(screen.getByLabelText(/Confirme a senha/), {
      target: { value: "senha-com-12+" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Criar conta" }).closest("form")!);

    await waitFor(() =>
      expect(registerPlayer).toHaveBeenCalledWith("novo_jogador", "senha-com-12+"),
    );
    expect(navigateMock).toHaveBeenCalledWith({ to: "/play" });
  });

  it("explains mismatched passwords without sending a registration request", async () => {
    render(<AccessPlaceholder mode="register" />);
    fireEvent.change(screen.getByLabelText(/Nome de usuário/), {
      target: { value: "novo_jogador" },
    });
    fireEvent.change(document.getElementById("player-password")!, {
      target: { value: "senha-com-12+" },
    });
    fireEvent.change(screen.getByLabelText(/Confirme a senha/), {
      target: { value: "outra-senha-12" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Criar conta" }).closest("form")!);

    expect(await screen.findByRole("alert")).toHaveTextContent("As senhas não conferem.");
    expect(registerPlayer).not.toHaveBeenCalled();
  });

  it("submits an existing account through the login flow", async () => {
    render(<AccessPlaceholder mode="login" />);
    fireEvent.change(screen.getByLabelText(/Nome de usuário/), {
      target: { value: "jogador_antigo" },
    });
    fireEvent.change(document.getElementById("player-password")!, {
      target: { value: "senha-antiga" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Entrar" }).closest("form")!);

    await waitFor(() => expect(loginPlayer).toHaveBeenCalledWith("jogador_antigo", "senha-antiga"));
    expect(navigateMock).toHaveBeenCalledWith({ to: "/play" });
  });
});

describe("administration and character-sheet regressions", () => {
  it("requires the password length accepted by the administrative login API", async () => {
    render(<AdminLoginPage />);
    expect(document.getElementById("admin-password")).toHaveAttribute("minLength", "12");
    fireEvent.change(screen.getByLabelText("Nome de usuário administrativo"), {
      target: { value: "mestre" },
    });
    fireEvent.change(document.getElementById("admin-password")!, {
      target: { value: "senha-admin-segura-2026" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Entrar no painel" }).closest("form")!);

    await waitFor(() =>
      expect(loginAdmin).toHaveBeenCalledWith("mestre", "senha-admin-segura-2026"),
    );
    expect(navigateMock).toHaveBeenCalledWith({ to: "/admin", replace: true });
  });

  it("uses Portuguese validation messages on the administrative login form", () => {
    render(<AdminLoginPage />);
    const username = document.getElementById("admin-username") as HTMLInputElement;

    fireEvent.invalid(username);

    expect(username.validationMessage).toBe("Este campo é obrigatório.");
  });

  it("loads the character sheet and preserves character renaming through its API", async () => {
    const onCharacterRenamed = vi.fn();
    render(
      <CharacterSheet
        campaignId={campaign.id}
        onBack={vi.fn()}
        onCharacterRenamed={onCharacterRenamed}
        onLogout={vi.fn()}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Personagem de teste" })).toBeVisible();
    expect(getCampaignCharacterSheet).toHaveBeenCalledWith(campaign.id);
    fireEvent.change(screen.getByLabelText("Renomear personagem"), {
      target: { value: "Novo nome" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvar nome" }));

    await waitFor(() =>
      expect(updateCampaignCharacter).toHaveBeenCalledWith(campaign.id, "Novo nome"),
    );
    expect(onCharacterRenamed).toHaveBeenCalledWith("Novo nome");
    expect(await screen.findByRole("status")).toHaveTextContent("Nome do personagem salvo.");
  });

  it("shows level progress and recorded level-up bonuses", async () => {
    vi.mocked(getCampaignCharacterSheet).mockResolvedValueOnce({
      ...characterSheet,
      xp: 150,
      xp_to_next_level: 300,
      xp_progress_percent: 50,
      attribute_points: 2,
      progression_history: [
        {
          id: "progression-event-1",
          created_at: "2026-11-02T18:00:00Z",
          source_type: "quest",
          source_id: "quest-1",
          source_name: "Encontrar a relíquia",
          xp_awarded: 350,
          xp_before: 0,
          xp_after: 150,
          level_before: 1,
          level_after: 3,
          gold_awarded: 20,
          attribute_points_awarded: 2,
          max_hp_increase: 10,
          max_mana_increase: 4,
          items: [{ item_id: "item-1", name: "Elixir", quantity: 1 }],
        },
      ],
    });

    render(
      <CharacterSheet
        campaignId={campaign.id}
        onBack={vi.fn()}
        onCharacterRenamed={vi.fn()}
        onLogout={vi.fn()}
      />,
    );

    expect(await screen.findByText("150 / 300 XP nesta faixa")).toBeVisible();
    expect(
      screen.getByRole("progressbar", {
        name: "Progresso de experiência para o próximo nível",
      }),
    ).toHaveAttribute("aria-valuenow", "150");
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Atributos e recursos" }), {
      button: 0,
      ctrlKey: false,
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Evolução: nível 1 → 3");
    expect(
      screen.getByText(/\+10 HP máximo · \+4 mana máxima · \+2 pontos de atributo/),
    ).toBeVisible();
    expect(screen.getByText("Origem: missão — Encontrar a relíquia")).toBeVisible();
    expect(screen.getByText("Itens: Elixir ×1")).toBeVisible();
  });

  it("shows available mission objectives and accepts through the server", async () => {
    vi.mocked(getCampaignQuests).mockResolvedValueOnce([
      {
        id: "quest-available",
        title: "Encontrar o mapa",
        description: "Explore a biblioteca.",
        status: "available",
        progress: {},
        objectives: [
          {
            id: "find-map",
            title: "Encontrar o mapa",
            description: "Procure nas estantes.",
            target: 1,
          },
        ],
        rewards: { xp: 25, gold: 3, items: [], skill_ids: [] },
      },
    ]);

    render(
      <CharacterSheet
        campaignId={campaign.id}
        onBack={vi.fn()}
        onCharacterRenamed={vi.fn()}
        onLogout={vi.fn()}
      />,
    );

    fireEvent.mouseDown(await screen.findByRole("tab", { name: "Missões" }), {
      button: 0,
      ctrlKey: false,
    });
    expect(await screen.findAllByText("Encontrar o mapa")).toHaveLength(2);
    expect(screen.getByText("0 / 1")).toBeVisible();
    expect(screen.getByText("Recompensas: 25 XP · 3 ouro")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Aceitar missão" }));
    await waitFor(() =>
      expect(acceptCampaignQuest).toHaveBeenCalledWith(campaign.id, "quest-available"),
    );
    expect(await screen.findByText(/Missão iniciada/)).toBeVisible();
    expect(screen.queryByRole("button", { name: /concluir missão/i })).not.toBeInTheDocument();
    await waitFor(() => expect(getCampaignQuests).toHaveBeenCalledTimes(2));
  });

  it("wraps long character names in the sheet header", async () => {
    const longName = `Personagem de qa_${"x".repeat(29)}`;
    vi.mocked(getCampaignCharacterSheet).mockResolvedValueOnce({
      ...characterSheet,
      name: longName,
    });

    render(
      <CharacterSheet
        campaignId={campaign.id}
        onBack={vi.fn()}
        onCharacterRenamed={vi.fn()}
        onLogout={vi.fn()}
      />,
    );

    expect(await screen.findByRole("heading", { name: longName })).toHaveClass("break-all");
  });

  it("shows an empty state when the API returns no inventory items", async () => {
    render(
      <CharacterSheet
        campaignId={campaign.id}
        onBack={vi.fn()}
        onCharacterRenamed={vi.fn()}
        onLogout={vi.fn()}
      />,
    );

    await screen.findByRole("heading", { name: "Personagem de teste" });
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Inventário e equipamentos" }), {
      button: 0,
      ctrlKey: false,
    });
    expect(await screen.findByText("Seu inventário ainda está vazio.")).toBeVisible();
  });

  it("associates administrative form errors with their fields and announces them", async () => {
    render(
      <EntityFormDialog
        open
        onOpenChange={vi.fn()}
        title="Novo conteúdo"
        fields={[{ name: "title", label: "Título", type: "text", required: true }]}
        initial={{ title: "" }}
        onSubmit={vi.fn()}
      />,
    );

    fireEvent.submit(screen.getByRole("button", { name: "Salvar" }).closest("form")!);

    const title = screen.getByLabelText(/Título/);
    expect(await screen.findByRole("alert")).toHaveTextContent("Campo obrigatório");
    expect(title).toHaveAttribute("aria-invalid", "true");
    expect(title).toHaveAttribute("aria-describedby", "f-title-error");
  });
});

describe("campaign onboarding", () => {
  it("shows useful empty guidance only after the campaign list loads", async () => {
    render(<CampaignsHomePage user={user} onLogout={vi.fn()} />);

    expect(await screen.findByText("Sua jornada ainda não começou")).toBeVisible();
    expect(screen.getByRole("link", { name: "Criar campanha" })).toHaveAttribute(
      "href",
      "#criar-campanha",
    );
    expect(screen.getByRole("link", { name: "Tenho um convite" })).toHaveAttribute(
      "href",
      "#entrar-campanha",
    );
    expect(screen.getByLabelText("Código da sala")).toHaveAttribute("maxLength", "32");
  });

  it("announces loading before rendering the empty campaign state", async () => {
    let resolveCampaigns: ((campaigns: Campaign[]) => void) | undefined;
    vi.mocked(listCampaigns).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveCampaigns = resolve;
      }),
    );
    render(<CampaignsHomePage user={user} onLogout={vi.fn()} />);

    expect(screen.getByRole("status")).toHaveTextContent("Carregando suas campanhas...");
    expect(screen.queryByText("Sua jornada ainda não começou")).not.toBeInTheDocument();
    resolveCampaigns?.([]);
    expect(await screen.findByText("Sua jornada ainda não começou")).toBeVisible();
  });

  it("does not mistake a failed campaign request for an empty account", async () => {
    vi.mocked(listCampaigns).mockRejectedValueOnce(new Error("Falha de conexão."));
    render(<CampaignsHomePage user={user} onLogout={vi.fn()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Falha de conexão.");
    expect(screen.queryByText("Sua jornada ainda não começou")).not.toBeInTheDocument();
  });

  it("creates a campaign and enters its existing lobby route", async () => {
    render(<CampaignsHomePage user={user} onLogout={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/Nome da campanha/), {
      target: { value: "Aventura do grupo" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Criar campanha" }).closest("form")!);

    await waitFor(() =>
      expect(createCampaign).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Aventura do grupo", max_players: 7 }),
      ),
    );
    expect(navigateMock).toHaveBeenCalledWith({
      to: "/campaigns/$campaignId",
      params: { campaignId: campaign.id },
    });
  });

  it("joins a campaign with the supplied invite code", async () => {
    render(<CampaignsHomePage user={user} onLogout={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Código da sala"), {
      target: { value: campaign.join_code.toLowerCase() },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Entrar na campanha" }).closest("form")!);

    await waitFor(() => expect(joinCampaign).toHaveBeenCalledWith(campaign.join_code));
    expect(navigateMock).toHaveBeenCalledWith({
      to: "/campaigns/$campaignId",
      params: { campaignId: campaign.id },
    });
  });

  it("shows the join error and keeps the player on the campaign dashboard", async () => {
    vi.mocked(joinCampaign).mockRejectedValueOnce(new Error("Convite inválido."));
    render(<CampaignsHomePage user={user} onLogout={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Código da sala"), {
      target: { value: "NAO-VALIDO" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Entrar na campanha" }).closest("form")!);

    expect(await screen.findByRole("alert")).toHaveTextContent("Convite inválido.");
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("confirms invitation and readiness actions accessibly in the lobby", async () => {
    render(<CampaignLobbyPage user={user} campaignId={campaign.id} onLogout={vi.fn()} />);

    expect(await screen.findByText("Convide participantes para a sala")).toBeVisible();
    expect(screen.getByText(campaign.join_code).classList.contains("break-all")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Marcar como pronto" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Você marcou que está pronto.");
    expect(updateCampaignReady).toHaveBeenCalledWith(campaign.id, true);
  });

  it("announces server-recorded adventure rewards in the lobby", async () => {
    const activeCampaign = { ...campaign, status: "in_progress" };
    const game: NarrativeGame = {
      session_id: "session-1",
      status: "running",
      chapter: {
        id: "chapter-1",
        title: "Capítulo de teste",
        summary: "",
        narrative: "",
      },
      scene: {
        id: "scene-1",
        title: "Cena de teste",
        narrative: "",
        choices: [],
      },
      participants: activeCampaign.members,
      vote: null,
      last_result: null,
      history: [
        {
          sequence_number: 4,
          actor_user_id: user.id,
          event_type: "rewards_granted",
          payload: {
            rewards: [
              {
                character_name: "Personagem de teste",
                xp: 100,
                gold: 15,
                items: [{ name: "Poção", quantity: 2 }],
              },
            ],
          },
          created_at: "2026-11-02T18:00:00Z",
        },
      ],
    };
    vi.mocked(getCampaign).mockResolvedValue(activeCampaign);
    vi.mocked(getNarrativeGame).mockResolvedValue(game);

    render(<CampaignLobbyPage user={user} campaignId={campaign.id} onLogout={vi.fn()} />);

    await waitFor(() => expect(getNarrativeGame).toHaveBeenCalled());
    expect(await screen.findByText("Capítulo de teste")).toBeVisible();
    expect(await screen.findByText("Recompensas recebidas")).toBeVisible();
    expect(screen.getByText("Personagem de teste: +100 XP · +15 ouro · Poção ×2")).toBeVisible();
  });

  it("does not overlap presence heartbeat requests when one is still pending", async () => {
    vi.useFakeTimers();
    const resolveHeartbeats: Array<() => void> = [];
    let activeHeartbeats = 0;
    let maximumActiveHeartbeats = 0;
    vi.mocked(updateCampaignPresence).mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          activeHeartbeats += 1;
          maximumActiveHeartbeats = Math.max(maximumActiveHeartbeats, activeHeartbeats);
          resolveHeartbeats.push(() => {
            activeHeartbeats -= 1;
            resolve();
          });
        }),
    );

    const { unmount } = render(
      <CampaignLobbyPage user={user} campaignId={campaign.id} onLogout={vi.fn()} />,
    );
    await act(async () => {
      await Promise.resolve();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(45_000);
    });

    expect(updateCampaignPresence).toHaveBeenCalledTimes(1);
    resolveHeartbeats[0]?.();
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(updateCampaignPresence).toHaveBeenCalledTimes(2);
    expect(maximumActiveHeartbeats).toBe(1);

    resolveHeartbeats[1]?.();
    unmount();
    vi.useRealTimers();
  });

  it("does not replace a newer readiness response with an older lobby poll", async () => {
    vi.useFakeTimers();
    let resolveOlderPoll: ((value: Campaign) => void) | undefined;
    vi.mocked(getCampaign)
      .mockResolvedValueOnce(campaign)
      .mockImplementationOnce(
        () =>
          new Promise<Campaign>((resolve) => {
            resolveOlderPoll = resolve;
          }),
      );

    render(<CampaignLobbyPage user={user} campaignId={campaign.id} onLogout={vi.fn()} />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText("Ainda não está pronto")).toBeVisible();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    expect(getCampaign).toHaveBeenCalledTimes(2);

    fireEvent.click(screen.getByRole("button", { name: "Marcar como pronto" }));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText("Pronto")).toBeVisible();

    await act(async () => {
      resolveOlderPoll?.(campaign);
      await Promise.resolve();
    });

    expect(screen.getByText("Pronto")).toBeVisible();
    vi.useRealTimers();
  });

  it("does not overlap campaign snapshot polls while a request is stalled", async () => {
    vi.useFakeTimers();
    let resolveStalledPoll: ((value: Campaign) => void) | undefined;
    vi.mocked(getCampaign)
      .mockResolvedValueOnce(campaign)
      .mockImplementationOnce(
        () =>
          new Promise<Campaign>((resolve) => {
            resolveStalledPoll = resolve;
          }),
      );

    const { unmount } = render(
      <CampaignLobbyPage user={user} campaignId={campaign.id} onLogout={vi.fn()} />,
    );
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(20_000);
    });
    expect(getCampaign).toHaveBeenCalledTimes(2);

    unmount();
    resolveStalledPoll?.(campaign);
    vi.useRealTimers();
  });

  it("retries after a temporary lobby error and clears the connection warning on recovery", async () => {
    vi.useFakeTimers();
    const recoveredCampaign = {
      ...campaign,
      members: [{ ...campaign.members[0]!, display_name: "Conexão recuperada" }],
    };
    vi.mocked(getCampaign)
      .mockResolvedValueOnce(campaign)
      .mockRejectedValueOnce(new Error("Falha temporária."))
      .mockResolvedValue(recoveredCampaign);

    render(<CampaignLobbyPage user={user} campaignId={campaign.id} onLogout={vi.fn()} />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText("Ainda não está pronto")).toBeVisible();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    expect(screen.getByRole("status")).toHaveTextContent(
      "Falha temporária. Tentando atualizar novamente...",
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    expect(screen.getByText("Conexão recuperada")).toBeVisible();
    expect(screen.queryByText(/Tentando atualizar novamente/)).not.toBeInTheDocument();
    vi.useRealTimers();
  });

  it("pauses lobby polling while the tab is hidden and refreshes when it becomes visible", async () => {
    vi.useFakeTimers();
    const visibilityDescriptor = Object.getOwnPropertyDescriptor(document, "visibilityState");
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "hidden",
    });

    const { unmount } = render(
      <CampaignLobbyPage user={user} campaignId={campaign.id} onLogout={vi.fn()} />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(getCampaign).not.toHaveBeenCalled();
    expect(updateCampaignPresence).not.toHaveBeenCalled();

    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });
    await act(async () => {
      fireEvent(document, new Event("visibilitychange"));
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText("Campanha de teste")).toBeVisible();
    expect(getCampaign).toHaveBeenCalledTimes(1);
    expect(updateCampaignPresence).toHaveBeenCalledTimes(1);

    unmount();
    if (visibilityDescriptor) {
      Object.defineProperty(document, "visibilityState", visibilityDescriptor);
    }
    vi.useRealTimers();
  });

  it("aborts an in-flight lobby request when the component unmounts", async () => {
    let requestSignal: AbortSignal | undefined;
    vi.mocked(getCampaign).mockImplementationOnce((_campaignId, signal) => {
      requestSignal = signal;
      return new Promise<Campaign>(() => {});
    });

    const { unmount } = render(
      <CampaignLobbyPage user={user} campaignId={campaign.id} onLogout={vi.fn()} />,
    );
    expect(requestSignal?.aborted).toBe(false);
    unmount();
    expect(requestSignal?.aborted).toBe(true);
  });

  it("renders disconnected presence from the authoritative campaign response", async () => {
    vi.mocked(getCampaign).mockResolvedValueOnce({
      ...campaign,
      members: [{ ...campaign.members[0]!, is_connected: false }],
    });

    render(<CampaignLobbyPage user={user} campaignId={campaign.id} onLogout={vi.fn()} />);

    expect(await screen.findByText("Desconectado")).toBeVisible();
  });

  it("synchronizes readiness between two independent lobby sessions", async () => {
    vi.useFakeTimers();
    const secondUser: AuthUser = {
      id: "player-2",
      username: "companheiro",
      display_name: "Companheiro",
    };
    let serverCampaign: Campaign = {
      ...campaign,
      participant_count: 2,
      available_slots: 3,
      members: [
        campaign.members[0]!,
        {
          ...campaign.members[0]!,
          user_id: secondUser.id,
          username: secondUser.username,
          display_name: secondUser.display_name,
          role: "player",
          is_ready: false,
        },
      ],
    };
    vi.mocked(getCampaign).mockImplementation(async () => structuredClone(serverCampaign));
    vi.mocked(updateCampaignReady).mockImplementation(async (_campaignId, isReady) => {
      serverCampaign = {
        ...serverCampaign,
        members: serverCampaign.members.map((member) =>
          member.user_id === secondUser.id ? { ...member, is_ready: isReady } : member,
        ),
      };
      return structuredClone(serverCampaign);
    });

    const { unmount } = render(
      <>
        <CampaignLobbyPage user={user} campaignId={campaign.id} onLogout={vi.fn()} />
        <CampaignLobbyPage user={secondUser} campaignId={campaign.id} onLogout={vi.fn()} />
      </>,
    );
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getAllByText("Companheiro")).toHaveLength(2);
    fireEvent.click(screen.getAllByRole("button", { name: "Marcar como pronto" })[1]!);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(updateCampaignReady).toHaveBeenCalledWith(campaign.id, true);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    expect(screen.getAllByText("Pronto")).toHaveLength(2);
    unmount();

    render(<CampaignLobbyPage user={secondUser} campaignId={campaign.id} onLogout={vi.fn()} />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText("Pronto")).toBeVisible();
    vi.useRealTimers();
  });

  it("wraps long invite codes and usernames in the lobby", async () => {
    const longUsername = `qa_${"x".repeat(29)}`;
    vi.mocked(getCampaign).mockResolvedValueOnce({
      ...campaign,
      is_owner: false,
      members: [
        {
          ...campaign.members[0]!,
          role: "player",
          username: longUsername,
          display_name: longUsername,
          character_name: `Personagem de ${longUsername}`,
        },
      ],
    });

    render(<CampaignLobbyPage user={user} campaignId={campaign.id} onLogout={vi.fn()} />);

    expect(await screen.findByText(campaign.join_code)).toHaveClass("break-all");
    expect(screen.getByText(`@${longUsername}`)).toHaveClass("break-all");
    expect(screen.getByText(`Personagem de ${longUsername}`)).toHaveClass("break-all");
    expect(screen.getByRole("article")).toHaveClass("min-w-0");
  });
});
