import { afterEach, describe, expect, it, vi } from "vitest";

import {
  castNarrativeVote,
  createCampaign,
  acceptCampaignQuest,
  getCampaign,
  getCampaignCharacterSheet,
  getCampaignQuests,
  getNarrativeGame,
  joinCampaign,
} from "../lib/auth-api";

const campaignResponse = {
  id: "c8f248c2-4628-4e8d-90fb-edbb733a6b60",
  title: "A Vigília de Cinzas",
  description: "Uma campanha persistente.",
  join_code: "7A91C2E4B608D35F10293847ABCDEF56",
  status: "waiting",
  owner_id: "dbfef088-3ebd-4c7b-8a25-69a9c5e1ece0",
  owner_display_name: "Aventureiro",
  min_players: 3,
  max_players: 5,
  participant_count: 1,
  available_slots: 4,
  current_chapter_id: null,
  current_node_id: null,
  last_activity_at: "2026-10-29T21:00:00Z",
  membership_status: "active",
  is_owner: true,
  members: [
    {
      user_id: "dbfef088-3ebd-4c7b-8a25-69a9c5e1ece0",
      username: "Aventureiro",
      display_name: "Aventureiro",
      role: "owner",
      is_ready: false,
      is_connected: true,
      character_id: "c427095d-7dc7-45ea-bd2e-72b325bda1fb",
      character_name: "Personagem de Aventureiro",
      level: 1,
      hp: 10,
      max_hp: 10,
      mana: 0,
      max_mana: 0,
    },
  ],
};

const narrativeResponse = {
  session_id: "8a236514-561f-4832-944e-b711c6f4a7b3",
  status: "running",
  chapter: {
    id: "c932ee7b-00a5-4525-9a9b-640676501541",
    title: "A Vigília de Cinzas",
    summary: "Uma história persistente.",
    narrative: "O sino ecoa sobre a cidade.",
  },
  scene: {
    id: "e832ee7b-00a5-4525-9a9b-640676501541",
    title: "A encruzilhada",
    narrative: "Duas trilhas se abrem.",
    choices: [
      {
        id: "f932ee7b-00a5-4525-9a9b-640676501541",
        label: "Seguir ao norte",
        position: 0,
        next_node_id: null,
        conditions: {},
        consequences: { description: "Uma fogueira guia o grupo." },
      },
    ],
  },
  participants: campaignResponse.members,
  vote: {
    status: "open",
    round_number: 1,
    deadline_at: null,
    allow_vote_change: true,
    eligible_count: 3,
    voted_count: 0,
    my_choice_id: null,
    tally: [
      {
        choice_id: "f932ee7b-00a5-4525-9a9b-640676501541",
        label: "Seguir ao norte",
        votes: 0,
      },
    ],
    result: null,
  },
  last_result: null,
  history: [
    {
      sequence_number: 1,
      actor_user_id: "dbfef088-3ebd-4c7b-8a25-69a9c5e1ece0",
      event_type: "campaign_started",
      payload: { scene_title: "A encruzilhada" },
      created_at: "2026-10-29T21:00:00Z",
    },
  ],
};

const characterSheetResponse = {
  name: "Elarion",
  description: "Guardião das antigas ruínas.",
  character_class: "Sentinela",
  ancestry: "Elfo",
  level: 4,
  xp: 275,
  xp_to_next_level: 400,
  xp_progress_percent: 68,
  attribute_points: 0,
  gold: 83,
  hp: 18,
  max_hp: 24,
  mana: 7,
  max_mana: 12,
  attributes: { forca: 8, vitalidade: 11 },
  inventory: [
    {
      item_id: "a1b77ada-1d3f-4fa9-8a33-5c0b9a2c7401",
      name: "Espada de treino",
      description: "Uma lâmina simples.",
      category: "weapon",
      rarity: "common",
      image_url: null,
      weight: 3,
      effects: { attack: 2 },
      quantity: 2,
      is_equipped: true,
      slot: "main_hand",
    },
  ],
  skills: [],
  quests: [],
  progression_history: [
    {
      id: "progression-1",
      created_at: "2026-10-29T21:00:00Z",
      source_type: "narrative",
      source_id: "c932ee7b-00a5-4525-9a9b-640676501541",
      source_name: "Recompensa da Vigília",
      xp_awarded: 100,
      xp_before: 0,
      xp_after: 0,
      level_before: 1,
      level_after: 2,
      gold_awarded: 5,
      attribute_points_awarded: 1,
      max_hp_increase: 5,
      max_mana_increase: 2,
      items: [{ item_id: "item-1", name: "Poção", quantity: 1 }],
    },
  ],
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("campaign API client", () => {
  it("creates campaigns through the authenticated API", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(campaignResponse), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const payload = {
      title: "A Vigília de Cinzas",
      description: "Uma campanha persistente.",
      max_players: 5,
    };

    const created = await createCampaign(payload);

    expect(created.id).toBe(campaignResponse.id);
    expect(created.join_code).toBe("7A91C2E4B608D35F10293847ABCDEF56");
    expect(created.members[0]?.character_name).toBe("Personagem de Aventureiro");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/campaigns",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify(payload),
      }),
    );
  });

  it("surfaces API validation details for malformed join codes", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: [
            {
              loc: ["body", "code"],
              msg: "Informe um código de campanha válido.",
              type: "value_error",
            },
          ],
        }),
        {
          status: 422,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    await expect(joinCampaign("not-a-code")).rejects.toThrow(
      "Informe um código de campanha válido.",
    );
  });

  it("loads the persisted narrative and casts a validated choice vote", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
      async () =>
        new Response(JSON.stringify(narrativeResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );

    const game = await getNarrativeGame(campaignResponse.id);
    const updated = await castNarrativeVote(
      campaignResponse.id,
      narrativeResponse.scene.choices[0]!.id,
    );

    expect(game.scene.title).toBe("A encruzilhada");
    expect(game.scene.choices[0]?.consequences["description"]).toBe("Uma fogueira guia o grupo.");
    expect(updated.vote?.eligible_count).toBe(3);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `http://localhost:8000/api/campaigns/${campaignResponse.id}/game`,
      expect.objectContaining({ method: "GET", credentials: "include" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `http://localhost:8000/api/campaigns/${campaignResponse.id}/game/vote`,
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({ choice_id: narrativeResponse.scene.choices[0]!.id }),
      }),
    );
  });

  it("passes abort signals to campaign polling requests", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(campaignResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const controller = new AbortController();

    await getCampaign(campaignResponse.id, controller.signal);

    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/api/campaigns/${campaignResponse.id}`,
      expect.objectContaining({ signal: controller.signal }),
    );
  });

  it("loads the authenticated player's character sheet as read-only data", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(characterSheetResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const sheet = await getCampaignCharacterSheet(campaignResponse.id);

    expect(sheet.name).toBe("Elarion");
    expect(sheet.hp).toBe(18);
    expect(sheet.inventory[0]?.quantity).toBe(2);
    expect(sheet.inventory[0]?.is_equipped).toBe(true);
    expect(sheet.progression_history[0]?.items[0]?.name).toBe("Poção");
    expect(sheet.progression_history[0]?.source_name).toBe("Recompensa da Vigília");
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/api/campaigns/${campaignResponse.id}/character`,
      expect.objectContaining({ method: "GET", credentials: "include" }),
    );
  });

  it("loads published missions and accepts one through the authenticated API", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "quest-1",
              title: "A chave esquecida",
              description: "Encontre a chave.",
              status: "available",
              progress: {},
              objectives: [
                {
                  id: "find-key",
                  title: "Encontrar a chave",
                  description: "Procure na biblioteca.",
                  target: 1,
                },
              ],
              rewards: { xp: 50, gold: 10, items: [], skill_ids: [] },
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ quest_id: "quest-1", status: "in_progress", progress: {} }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    const quests = await getCampaignQuests(campaignResponse.id);
    await acceptCampaignQuest(campaignResponse.id, "quest-1");

    expect(quests[0]?.status).toBe("available");
    expect(quests[0]?.objectives[0]?.target).toBe(1);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `http://localhost:8000/api/campaigns/${campaignResponse.id}/quests`,
      expect.objectContaining({ method: "GET", credentials: "include" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `http://localhost:8000/api/campaigns/${campaignResponse.id}/quests/quest-1/accept`,
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: "{}",
      }),
    );
  });
});
