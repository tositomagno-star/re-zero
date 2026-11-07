import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const combatApi = vi.hoisted(() => ({
  getCombatAsset: vi.fn(),
  getLatestCombat: vi.fn(),
  listCombatEnemies: vi.fn(),
  resolveCombatAction: vi.fn(),
  startCombat: vi.fn(),
  submitCombatAction: vi.fn(),
}));

vi.mock("@/lib/combat-api", () => combatApi);
import { CombatPanel } from "@/components/player/CombatPanel";
import type { Campaign, AuthUser } from "@/lib/auth-api";
import type { CombatEncounter } from "@/lib/combat-api";

const ownerId = "user-1";
const characterId = "character-1";
const enemyId = "enemy-1";
const characterCombatantId = "combatant-character";
const enemyCombatantId = "combatant-enemy";

const attackAnimation = {
  id: "animation-1",
  name: "Ataque",
  asset_id: "asset-animation",
  impact_asset_id: null,
  animation_type: "projectile",
  trajectory: "origin_to_target",
  movement: "linear",
  origin: { x: 0.9, y: 0.5 },
  target: { x: 0.2, y: 0.5 },
  scale: 1,
  rotation: 0,
  gif_playback_rate: 1,
  travel_duration_ms: 300,
  travel_speed: 1,
  impact_time_ms: 0,
  render_layer: 10,
  direction: "auto",
  extra: {},
  release_delay_ms: 60,
  animation_duration_ms: 140,
  actor_id: characterCombatantId,
  target_id: enemyCombatantId,
  actor_animation_asset_id: "asset-actor-animation",
  attack_asset_id: "asset-attack-animation",
};

function battle(overrides: Partial<CombatEncounter> = {}): CombatEncounter {
  return {
    id: "battle-1",
    title: "Batalha: Goblin",
    status: "in_progress",
    version: 1,
    active_combatant_id: characterCombatantId,
    round: 1,
    result: null,
    reward_status: "pending",
    combatants: [
      {
        id: characterCombatantId,
        character_id: characterId,
        enemy_id: null,
        name: "Aventureiro",
        current_hp: 10,
        max_hp: 10,
        current_mana: 3,
        max_mana: 3,
        initiative: 5,
        is_active: true,
        is_enemy: false,
        snapshot: { skills: {} },
        conditions: {},
      },
      {
        id: enemyCombatantId,
        character_id: null,
        enemy_id: enemyId,
        name: "Goblin",
        current_hp: 5,
        max_hp: 5,
        current_mana: 0,
        max_mana: 0,
        initiative: 1,
        is_active: false,
        is_enemy: true,
        snapshot: {},
        conditions: {},
      },
    ],
    events: [],
    last_sequence: 0,
    ...overrides,
  };
}

const campaign = {
  id: "campaign-1",
  owner_id: ownerId,
  status: "in_progress",
  members: [{ user_id: ownerId, character_id: characterId }],
} as Campaign;
const user = { id: ownerId, username: "player", display_name: "Player" } as AuthUser;

afterEach(() => {
  vi.clearAllMocks();
});

describe("combat panel", () => {
  it("submits an action once and animation completion never applies damage", async () => {
    combatApi.getLatestCombat.mockResolvedValue(battle());
    combatApi.listCombatEnemies.mockResolvedValue([]);
    combatApi.getCombatAsset.mockResolvedValue(new Blob(["gif"]));
    combatApi.submitCombatAction.mockResolvedValue(
      battle({
        version: 2,
        pending_action: {
          action_id: "action-id",
          actor_id: characterCombatantId,
          target_id: enemyCombatantId,
        },
        events: [
          {
            sequence: 1,
            type: "action_started",
            created_at: "2026-01-01T00:00:00Z",
            payload: {
              action_id: "action-id",
              actor_name: "Aventureiro",
              target_name: "Goblin",
              visual: attackAnimation,
            },
          },
        ],
        last_sequence: 1,
      }),
    );
    combatApi.resolveCombatAction.mockResolvedValue(
      battle({
        status: "victory",
        result: "victory",
        version: 3,
        active_combatant_id: null,
        pending_action: null,
        combatants: battle().combatants.map((combatant) =>
          combatant.id === enemyCombatantId ? { ...combatant, current_hp: 0 } : combatant,
        ),
        events: [
          {
            sequence: 1,
            type: "action_started",
            created_at: "2026-01-01T00:00:00Z",
            payload: {
              action_id: "action-id",
              actor_name: "Aventureiro",
              target_name: "Goblin",
              visual: attackAnimation,
            },
          },
          {
            sequence: 2,
            type: "action_resolved",
            created_at: "2026-01-01T00:00:00Z",
            payload: {
              action: "attack",
              damage: 5,
              visual: { damage: 5 },
            },
          },
        ],
        last_sequence: 2,
      }),
    );

    render(<CombatPanel campaign={campaign} user={user} />);
    await screen.findByRole("option", { name: /Goblin/ });
    fireEvent.change(screen.getByLabelText("Alvo do combate"), {
      target: { value: enemyCombatantId },
    });
    const attackButton = screen.getByRole("button", { name: "Atacar" });
    act(() => {
      fireEvent.click(attackButton);
      fireEvent.click(attackButton);
    });

    await screen.findByText("Animação do personagem");
    expect(combatApi.resolveCombatAction).not.toHaveBeenCalled();
    expect(combatApi.getCombatAsset).toHaveBeenCalledWith(campaign.id, "asset-actor-animation");
    expect(combatApi.getCombatAsset).toHaveBeenCalledWith(campaign.id, "asset-attack-animation");
    expect(screen.queryByLabelText("Arena de pré-visualização")).not.toBeInTheDocument();
    expect(await screen.findByAltText("Projétil de Aventureiro")).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(combatApi.resolveCombatAction).not.toHaveBeenCalled();
    expect(combatApi.submitCombatAction).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(combatApi.resolveCombatAction).toHaveBeenCalledTimes(1));
    expect(screen.getByText("HP 0/5 · Mana 0/0")).toBeInTheDocument();
  });

  it("uses blue frames for allies and red frames for enemies", async () => {
    combatApi.getLatestCombat.mockResolvedValue(battle());
    combatApi.listCombatEnemies.mockResolvedValue([]);
    combatApi.getCombatAsset.mockResolvedValue(new Blob(["gif"]));

    render(<CombatPanel campaign={campaign} user={user} />);

    await screen.findByText("Aventureiro");
    expect(screen.getByLabelText("Jogador Aventureiro")).toHaveClass("border-blue-500/70");
    expect(screen.getByLabelText("Inimigo Goblin")).toHaveClass("border-red-500/70");
  });

  it("plays only the projectile when the action is configured for projectile-only visuals", async () => {
    const pendingEvent = {
      sequence: 1,
      type: "action_started",
      created_at: "2026-01-01T00:00:00Z",
      payload: {
        action_id: "projectile-action",
        actor_id: characterCombatantId,
        target_id: enemyCombatantId,
        actor_name: "Aventureiro",
        target_name: "Goblin",
        visual: {
          actor_id: characterCombatantId,
          target_id: enemyCombatantId,
          actor_animation_asset_id: null,
          attack_asset_id: "projectile-gif",
          projectile_only: true,
          release_delay_ms: 100,
          animation_duration_ms: 60,
        },
      },
    };
    combatApi.getLatestCombat.mockResolvedValue(
      battle({
        pending_action: {
          action_id: "projectile-action",
          actor_id: characterCombatantId,
          target_id: enemyCombatantId,
        },
        events: [pendingEvent],
        last_sequence: 1,
      }),
    );
    combatApi.listCombatEnemies.mockResolvedValue([]);
    combatApi.getCombatAsset.mockResolvedValue(new Blob(["gif"]));
    combatApi.resolveCombatAction.mockResolvedValue(battle());

    render(<CombatPanel campaign={campaign} user={user} />);

    expect(await screen.findByText("Preparação do projétil")).toBeInTheDocument();
    expect(await screen.findByAltText("Projétil de Aventureiro")).toBeInTheDocument();
    expect(combatApi.getCombatAsset).toHaveBeenCalledTimes(1);
    expect(combatApi.getCombatAsset).toHaveBeenCalledWith(campaign.id, "projectile-gif");
    await waitFor(() => expect(combatApi.resolveCombatAction).toHaveBeenCalledTimes(1));
  });

  it("resumes a pending action after reload and resolves once with GIF fallbacks", async () => {
    const pendingEvent = {
      sequence: 1,
      type: "action_started",
      created_at: "2026-01-01T00:00:00Z",
      payload: {
        action_id: "resumed-action",
        actor_name: "Aventureiro",
        target_name: "Goblin",
        visual: {
          actor_animation_asset_id: null,
          attack_asset_id: null,
          release_delay_ms: 0,
          animation_duration_ms: 80,
        },
      },
    };
    const pendingBattle = battle({
      pending_action: {
        action_id: "resumed-action",
        actor_id: characterCombatantId,
        target_id: enemyCombatantId,
      },
      events: [pendingEvent],
      last_sequence: 1,
    });
    combatApi.getLatestCombat.mockResolvedValue(pendingBattle);
    combatApi.listCombatEnemies.mockResolvedValue([]);
    combatApi.resolveCombatAction.mockResolvedValue(
      battle({
        version: 2,
        pending_action: null,
        events: [
          pendingEvent,
          {
            sequence: 2,
            type: "action_resolved",
            created_at: "2026-01-01T00:00:00Z",
            payload: { action_id: "resumed-action", damage: 0 },
          },
        ],
        last_sequence: 2,
      }),
    );

    render(<CombatPanel campaign={campaign} user={user} />);

    await screen.findByText("Animação do personagem");
    await waitFor(() => expect(combatApi.resolveCombatAction).toHaveBeenCalledTimes(1));
    expect(combatApi.resolveCombatAction).toHaveBeenCalledWith(
      campaign.id,
      "battle-1",
      "resumed-action",
    );
    expect(combatApi.getCombatAsset).not.toHaveBeenCalled();
    expect(combatApi.submitCombatAction).not.toHaveBeenCalled();
  });
});
