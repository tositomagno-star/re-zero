import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { adminContentRequest } = vi.hoisted(() => ({ adminContentRequest: vi.fn() }));
vi.mock("@/lib/admin-content-api", () => ({ adminContentRequest }));

import { CombatBalancePage } from "@/components/admin/CombatBalancePage";

const initialRules = Array.from({ length: 7 }, (_, index) => ({
  player_count: index + 1,
  enemies: { hp: 1, attack: 1, defense: 1 },
  bosses: { hp: 1, attack: 1, defense: 1 },
}));

afterEach(() => {
  vi.clearAllMocks();
});

describe("combat balance page", () => {
  it("edits and saves the boss multiplier for the selected party size", async () => {
    adminContentRequest.mockImplementation(
      async (_path: string, method?: string, body?: unknown) =>
        method === "PUT" ? body : { rules: initialRules },
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <CombatBalancePage />
      </QueryClientProvider>,
    );

    const bossHp = await screen.findByLabelText("7 jogadores · Bosses e minibosses · Vida (%)");
    fireEvent.change(bossHp, { target: { value: "150" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar balanceamento" }));

    await waitFor(() =>
      expect(adminContentRequest).toHaveBeenCalledWith(
        "/api/admin/combat-balance",
        "PUT",
        expect.objectContaining({
          rules: expect.arrayContaining([
            expect.objectContaining({
              player_count: 7,
              bosses: expect.objectContaining({ hp: 1.5 }),
            }),
          ]),
        }),
      ),
    );
  });
});
