import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { adminContentRequest } = vi.hoisted(() => ({
  adminContentRequest: vi.fn(),
}));

vi.mock("@/lib/admin-content-api", () => ({ adminContentRequest }));

import { MissionManagementPage } from "@/components/admin/MissionManagementPage";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MissionManagementPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("mission management page", () => {
  it("creates campaign mission objectives and backend-defined rewards", async () => {
    adminContentRequest.mockImplementation(async (path: string) => {
      if (path === "/api/admin/content/campaigns")
        return [{ id: "campaign-1", title: "A Vigília" }];
      if (path === "/api/admin/content/quests") return [];
      if (path === "/api/admin/content/items") return [{ id: "item-1", name: "Poção" }];
      if (path === "/api/admin/content/skills") return [];
      if (path === "/api/admin/content/quests")
        return [{ id: "quest-1", campaign_id: "campaign-1" }];
      return [];
    });

    renderPage();

    expect(await screen.findByText("Nenhuma missão cadastrada.")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Campanha"), {
      target: { value: "campaign-1" },
    });
    fireEvent.change(screen.getByLabelText("Título"), {
      target: { value: "Recuperar a insígnia" },
    });
    fireEvent.change(screen.getByLabelText("Descrição"), {
      target: { value: "Encontre a insígnia perdida." },
    });
    fireEvent.change(
      screen.getByLabelText("Objetivos (um por linha: ID único | título | descrição | meta)"),
      {
        target: {
          value: "find-insignia | Encontrar a insígnia | Procure na torre | 1",
        },
      },
    );
    fireEvent.change(screen.getByLabelText("Recompensa de XP"), {
      target: { value: "75" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Criar missão" }));

    await waitFor(() =>
      expect(adminContentRequest).toHaveBeenCalledWith(
        "/api/admin/content/quests",
        "POST",
        expect.objectContaining({
          campaign_id: "campaign-1",
          title: "Recuperar a insígnia",
          conditions: {
            objectives: [
              {
                id: "find-insignia",
                title: "Encontrar a insígnia",
                description: "Procure na torre",
                target: 1,
              },
            ],
            require_all_objectives: true,
          },
          rewards: {
            xp: 75,
            gold: 0,
            items: [],
            skill_ids: [],
          },
        }),
      ),
    );
  });
});
