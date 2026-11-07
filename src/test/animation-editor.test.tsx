import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const {
  deleteAnimationConfiguration,
  getAdminAssetFile,
  listAssetAssociationOptions,
  listAssets,
  listAnimationConfigurations,
  saveAnimationConfiguration,
} = vi.hoisted(() => ({
  deleteAnimationConfiguration: vi.fn(),
  getAdminAssetFile: vi.fn(),
  listAssetAssociationOptions: vi.fn(),
  listAssets: vi.fn(),
  listAnimationConfigurations: vi.fn(),
  saveAnimationConfiguration: vi.fn(),
}));

vi.mock("@/lib/admin-content-api", () => ({
  deleteAnimationConfiguration,
  getAdminAssetFile,
  listAssetAssociationOptions,
  listAssets,
  listAnimationConfigurations,
  saveAnimationConfiguration,
}));

import { AnimationEditorPage } from "@/components/admin/AnimationEditorPage";

const gifAsset = {
  id: "asset-gif",
  name: "Chama",
  content_type: "image/gif",
  extension: ".gif",
};

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AnimationEditorPage />
    </QueryClientProvider>,
  );
}

function validGifBlob(): Blob {
  return new Blob(["invalid gif bytes"], { type: "image/gif" });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

describe("animation editor", () => {
  it("edits normalized trajectory points and saves the independent timing values", async () => {
    listAnimationConfigurations.mockResolvedValue([]);
    listAssets.mockResolvedValue([gifAsset]);
    listAssetAssociationOptions.mockResolvedValue([]);
    getAdminAssetFile.mockResolvedValue(validGifBlob());
    saveAnimationConfiguration.mockImplementation(async (configuration) => ({
      ...configuration,
      id: "animation-1",
      is_in_use: false,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    }));

    renderPage();
    await screen.findAllByRole("option", { name: "Chama" });
    fireEvent.change(await screen.findByLabelText("GIF principal"), {
      target: { value: "asset-gif" },
    });
    fireEvent.change(screen.getByLabelText("Nome"), {
      target: { value: "Projétil de teste" },
    });
    fireEvent.change(screen.getByLabelText("Trajetória"), {
      target: { value: "right_to_left" },
    });
    expect(screen.getByLabelText("origin x")).toHaveValue(0.95);
    expect(screen.getByLabelText("target x")).toHaveValue(0.05);

    fireEvent.change(screen.getByLabelText("origin x"), {
      target: { value: "0.8" },
    });
    fireEvent.change(screen.getByLabelText("Velocidade de reprodução do GIF (×)"), {
      target: { value: "2" },
    });
    fireEvent.change(screen.getByLabelText(/Duração do deslocamento/), {
      target: { value: "1200" },
    });
    fireEvent.change(screen.getByLabelText("Velocidade de deslocamento (×)"), {
      target: { value: "1.25" },
    });
    fireEvent.change(screen.getByLabelText("Tempo de impacto (ms)"), {
      target: { value: "300" },
    });
    const saveButton = screen.getByRole("button", { name: "Salvar configuração" });
    await waitFor(() => expect(saveButton).toBeEnabled());
    fireEvent.click(saveButton);

    await waitFor(() =>
      expect(saveAnimationConfiguration).toHaveBeenCalledWith(
        expect.objectContaining({
          trajectory: "right_to_left",
          origin: { x: 0.8, y: 0.5 },
          gif_playback_rate: 2,
          travel_duration_ms: 1200,
          travel_speed: 1.25,
          impact_time_ms: 300,
        }),
        undefined,
      ),
    );
  });

  it("loads saved configurations after querying the backend and exposes replay controls", async () => {
    const saved = {
      id: "animation-saved",
      name: "Raio",
      description: "",
      asset_id: "asset-gif",
      impact_asset_id: null,
      animation_type: "projectile",
      trajectory: "left_to_right",
      movement: "linear",
      origin: { x: 0.05, y: 0.5 },
      target: { x: 0.95, y: 0.5 },
      scale: 1,
      rotation: 0,
      gif_playback_rate: 1,
      travel_duration_ms: 700,
      travel_speed: 0.75,
      impact_time_ms: 0,
      render_layer: 10,
      direction: "auto",
      extra: {},
      associations: [],
      is_in_use: false,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    listAnimationConfigurations.mockResolvedValue([saved]);
    listAssets.mockResolvedValue([gifAsset]);
    listAssetAssociationOptions.mockResolvedValue([]);
    getAdminAssetFile.mockResolvedValue(validGifBlob());
    const revokeObjectUrl = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:animation-preview"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: revokeObjectUrl,
    });

    const page = renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /Raio/ }));
    const playButton = await screen.findByRole("button", { name: /Reproduzir \/ repetir/ });
    const stopButton = screen.getByRole("button", { name: /Interromper/ });
    expect(stopButton).toBeDisabled();
    expect(screen.getByLabelText(/Duração do deslocamento/)).toHaveValue(700);
    const arena = screen.getByLabelText("Arena de pré-visualização");
    expect(arena.className).toContain("aspect-video");
    fireEvent.change(screen.getByLabelText("Cenário da arena"), {
      target: { value: "night" },
    });
    fireEvent.click(playButton);
    expect(stopButton).toBeEnabled();
    fireEvent.click(stopButton);
    expect(stopButton).toBeDisabled();
    fireEvent.click(playButton);
    expect(stopButton).toBeEnabled();
    page.unmount();
    expect(revokeObjectUrl).toHaveBeenCalledWith("blob:animation-preview");
  });
});
