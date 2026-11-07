import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { adminContentRequest, createAsset, listAnimationConfigurations, listAssets } = vi.hoisted(
  () => ({
    adminContentRequest: vi.fn(),
    createAsset: vi.fn(),
    listAnimationConfigurations: vi.fn(),
    listAssets: vi.fn(),
  }),
);

vi.mock("@/lib/admin-content-api", () => ({
  adminContentRequest,
  createAsset,
  listAnimationConfigurations,
  listAssets,
}));

import { EntityProfileEditor } from "@/components/admin/EntityProfileEditor";

function renderEditor(entityType: "enemy" | "skill" = "enemy") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <EntityProfileEditor entityType={entityType} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("entity profile editor", () => {
  it("saves a boss profile with H1 assets and per-attack speed", async () => {
    adminContentRequest.mockImplementation(
      async (path: string, method?: string, body?: unknown) => {
        if (method === "PUT") return body;
        if (path === "/api/admin/content/monsters") {
          return [{ id: "enemy-1", name: "Guardião do vale" }];
        }
        if (path === "/api/admin/content/profiles/enemy") return [];
        if (path === "/api/admin/content/skills") {
          return [{ id: "skill-1", name: "Investida", is_active: true, status: "published" }];
        }
        if (path === "/api/admin/content/items") return [];
        throw new Error(`Unexpected request: ${path}`);
      },
    );
    listAssets.mockResolvedValue([
      {
        id: "asset-1",
        name: "Sprite do Guardião",
        content_type: "image/png",
        extension: ".png",
      },
    ]);
    listAnimationConfigurations.mockResolvedValue([]);

    renderEditor();
    fireEvent.change(await screen.findByLabelText("Entidade"), {
      target: { value: "enemy-1" },
    });
    fireEvent.change(await screen.findByLabelText("Disponibilidade"), {
      target: { value: "available" },
    });
    fireEvent.change(screen.getByLabelText("Classe"), {
      target: { value: "boss" },
    });
    fireEvent.change(screen.getByLabelText("Dificuldade"), {
      target: { value: "hard" },
    });
    fireEvent.change(screen.getByLabelText("Máximo de ataques por turno"), {
      target: { value: "2" },
    });
    fireEvent.change(screen.getByLabelText("Pode interromper turnos"), {
      target: { value: "true" },
    });
    fireEvent.change(screen.getByLabelText("Tempo até liberar ataque (ms)"), {
      target: { value: "1300" },
    });
    fireEvent.change(screen.getByLabelText("Duração da animação (ms)"), {
      target: { value: "900" },
    });
    fireEvent.change(screen.getByLabelText("Velocidade padrão de ataque"), {
      target: { value: "1.5" },
    });
    fireEvent.change(screen.getByLabelText("Sprite"), {
      target: { value: "asset-1" },
    });
    fireEvent.click(await screen.findByLabelText("Investida"));
    fireEvent.change(screen.getByLabelText("Velocidade de ataque de Investida"), {
      target: { value: "0.75" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Criar configuração" }));

    await waitFor(() =>
      expect(adminContentRequest).toHaveBeenCalledWith(
        "/api/admin/content/profiles/enemy/enemy-1",
        "PUT",
        expect.objectContaining({
          availability: "available",
          settings: expect.objectContaining({
            category: "boss",
            default_attack_speed: 1.5,
            boss_difficulty: "hard",
            max_attacks_per_turn: 2,
            can_interrupt_turns: true,
            attack_release_delay_ms: 1300,
            attack_animation_duration_ms: 900,
          }),
          assets: [{ role: "sprite", asset_id: "asset-1" }],
          skills: [{ skill_id: "skill-1", attack_speed_override: 0.75 }],
        }),
      ),
    );
  });

  it("renders a load error instead of pretending the entity list is available", async () => {
    adminContentRequest.mockRejectedValue(new Error("API indisponível"));
    listAssets.mockResolvedValue([]);
    listAnimationConfigurations.mockResolvedValue([]);

    renderEditor();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível carregar as entidades. API indisponível",
    );
  });

  it("saves a skill configured to show only its projectile", async () => {
    adminContentRequest.mockImplementation(
      async (path: string, method?: string, body?: unknown) => {
        if (method === "PUT") return body;
        if (path === "/api/admin/content/skills") {
          return [{ id: "skill-1", name: "Lança arcana" }];
        }
        if (path === "/api/admin/content/profiles/skill") return [];
        if (path === "/api/admin/content/items") return [];
        throw new Error(`Unexpected request: ${path}`);
      },
    );
    listAssets.mockResolvedValue([]);
    listAnimationConfigurations.mockResolvedValue([]);

    renderEditor("skill");
    fireEvent.change(await screen.findByLabelText("Entidade"), {
      target: { value: "skill-1" },
    });
    fireEvent.change(await screen.findByLabelText("Animação da habilidade"), {
      target: { value: "true" },
    });
    fireEvent.click(await screen.findByRole("button", { name: "Criar configuração" }));

    await waitFor(() =>
      expect(adminContentRequest).toHaveBeenCalledWith(
        "/api/admin/content/profiles/skill/skill-1",
        "PUT",
        expect.objectContaining({
          settings: expect.objectContaining({ projectile_only: true }),
        }),
      ),
    );
  });

  it("saves separate execution and projectile GIFs for a skill", async () => {
    adminContentRequest.mockImplementation(
      async (path: string, method?: string, body?: unknown) => {
        if (method === "PUT") return body;
        if (path === "/api/admin/content/skills") {
          return [{ id: "skill-1", name: "Lança arcana" }];
        }
        if (path === "/api/admin/content/profiles/skill") return [];
        if (path === "/api/admin/content/items") return [];
        throw new Error(`Unexpected request: ${path}`);
      },
    );
    listAssets.mockResolvedValue([
      { id: "execution-gif", name: "Execução", content_type: "image/gif", extension: ".gif" },
      { id: "projectile-gif", name: "Projétil", content_type: "image/gif", extension: ".gif" },
    ]);
    listAnimationConfigurations.mockResolvedValue([]);

    renderEditor("skill");
    fireEvent.change(await screen.findByLabelText("Entidade"), {
      target: { value: "skill-1" },
    });
    fireEvent.change(await screen.findByLabelText("GIF de execução"), {
      target: { value: "execution-gif" },
    });
    fireEvent.change(screen.getByLabelText("GIF do projétil"), {
      target: { value: "projectile-gif" },
    });
    fireEvent.click(await screen.findByRole("button", { name: "Criar configuração" }));

    await waitFor(() =>
      expect(adminContentRequest).toHaveBeenCalledWith(
        "/api/admin/content/profiles/skill/skill-1",
        "PUT",
        expect.objectContaining({
          settings: expect.objectContaining({ combat_visual_mode: "separated" }),
          assets: [
            { role: "attack", asset_id: "execution-gif" },
            { role: "impact", asset_id: "projectile-gif" },
          ],
        }),
      ),
    );
  });

  it("uploads a GIF directly from the execution slot and selects it", async () => {
    adminContentRequest.mockImplementation(
      async (path: string, method?: string, body?: unknown) => {
        if (method === "PUT") return body;
        if (path === "/api/admin/content/skills") {
          return [{ id: "skill-1", name: "Lança arcana" }];
        }
        if (path === "/api/admin/content/profiles/skill") return [];
        if (path === "/api/admin/content/items") return [];
        throw new Error(`Unexpected request: ${path}`);
      },
    );
    const uploaded = {
      id: "uploaded-execution",
      name: "Execução",
      content_type: "image/gif",
      extension: ".gif",
    };
    listAssets.mockResolvedValue([uploaded]);
    createAsset.mockResolvedValue(uploaded);
    listAnimationConfigurations.mockResolvedValue([]);

    renderEditor("skill");
    fireEvent.change(await screen.findByLabelText("Entidade"), {
      target: { value: "skill-1" },
    });
    const gif = new File(["GIF89a"], "execucao.gif", { type: "image/gif" });
    fireEvent.change(screen.getByLabelText("Enviar GIF de execução"), {
      target: { files: [gif] },
    });

    await waitFor(() =>
      expect(createAsset).toHaveBeenCalledWith(
        gif,
        expect.objectContaining({
          category: "spells",
          subcategory: "execution",
          asset_type: "execution_gif",
          associations: [{ entity_type: "skill", entity_id: "skill-1" }],
        }),
      ),
    );
    fireEvent.click(await screen.findByRole("button", { name: "Criar configuração" }));

    await waitFor(() =>
      expect(adminContentRequest).toHaveBeenCalledWith(
        "/api/admin/content/profiles/skill/skill-1",
        "PUT",
        expect.objectContaining({
          assets: [{ role: "attack", asset_id: "uploaded-execution" }],
        }),
      ),
    );
  });
});
