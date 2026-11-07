import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getCombatBalanceSettings,
  updateCombatBalanceSettings,
  type CombatBalanceSettings,
} from "@/lib/combat-balance-api";

const settings: CombatBalanceSettings = {
  rules: Array.from({ length: 7 }, (_, index) => ({
    player_count: index + 1,
    enemies: { hp: 1, attack: 1, defense: 1 },
    bosses: { hp: 1, attack: 1, defense: 1 },
  })),
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("combat balance API", () => {
  it("loads and validates rules for all seven party sizes", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(settings), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(getCombatBalanceSettings()).resolves.toEqual(settings);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/admin/combat-balance",
      expect.objectContaining({ method: "GET", credentials: "include" }),
    );
  });

  it("saves the full balance configuration through the admin API", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(settings), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(updateCombatBalanceSettings(settings)).resolves.toEqual(settings);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/admin/combat-balance",
      expect.objectContaining({
        method: "PUT",
        credentials: "include",
        body: JSON.stringify(settings),
      }),
    );
  });

  it("rejects incomplete or out-of-order balance rules", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ rules: settings.rules.slice(0, 6) }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(getCombatBalanceSettings()).rejects.toThrow(
      "A API retornou regras de balanceamento inválidas.",
    );
  });
});
