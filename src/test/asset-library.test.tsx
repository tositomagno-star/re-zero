import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const {
  createAsset,
  deleteAsset,
  getAdminAssetFile,
  listAssetAssociationOptions,
  listAssets,
  replaceAssetFile,
  updateAssetMetadata,
} = vi.hoisted(() => ({
  createAsset: vi.fn(),
  deleteAsset: vi.fn(),
  getAdminAssetFile: vi.fn(),
  listAssetAssociationOptions: vi.fn(),
  listAssets: vi.fn(),
  replaceAssetFile: vi.fn(),
  updateAssetMetadata: vi.fn(),
}));

vi.mock("@/lib/admin-content-api", () => ({
  createAsset,
  deleteAsset,
  getAdminAssetFile,
  listAssetAssociationOptions,
  listAssets,
  replaceAssetFile,
  updateAssetMetadata,
}));

import { AssetLibraryPage } from "@/components/admin/AssetLibraryPage";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AssetLibraryPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("asset library page", () => {
  it("submits user-defined subcategory and asset type with the image", async () => {
    listAssets.mockResolvedValue([]);
    listAssetAssociationOptions.mockResolvedValue([]);
    createAsset.mockResolvedValue({});
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:asset-preview"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Novo asset" }));
    fireEvent.change(screen.getByLabelText("Nome"), {
      target: { value: "Efeito de impacto azul" },
    });
    fireEvent.change(screen.getByLabelText("Subcategoria (opcional)"), {
      target: { value: "elementais personalizados" },
    });
    fireEvent.change(screen.getByLabelText("Tipo específico (opcional)"), {
      target: { value: "impacto" },
    });
    fireEvent.click(screen.getByLabelText(/Disponibilizar arquivo publicamente/));
    const file = new File(["gif"], "impact.gif", { type: "image/gif" });
    fireEvent.change(screen.getByLabelText("Arquivo de imagem"), {
      target: { files: [file] },
    });
    expect(await screen.findByText("impact.gif")).toBeVisible();
    const form = screen.getByLabelText("Nome").closest("form");
    if (!form) throw new Error("Asset form is not available.");
    fireEvent.submit(form);

    await waitFor(() =>
      expect(createAsset).toHaveBeenCalledWith(
        file,
        expect.objectContaining({
          name: "Efeito de impacto azul",
          category: "characters",
          subcategory: "elementais personalizados",
          asset_type: "impacto",
          is_public: true,
          associations: [],
        }),
      ),
    );
  });

  it("shows measured GIF frame and timing metadata in the detail view", async () => {
    const gifAsset = {
      id: "asset-gif",
      name: "Explosão",
      description: "",
      category: "visual_effects",
      subcategory: "elementais",
      asset_type: "impacto",
      is_public: false,
      is_in_use: false,
      original_filename: "explosion.gif",
      content_type: "image/gif",
      extension: ".gif",
      width: 4,
      height: 3,
      size_bytes: 128,
      analysis_metadata: {
        aspect_ratio: 1.333333,
        has_transparency: true,
        gif: {
          frame_count: 2,
          total_duration_ms: 200,
          frame_durations_ms: [100, 100],
          loop: 0,
        },
      },
      created_at: "2026-11-03T10:00:00Z",
      updated_at: "2026-11-03T10:00:00Z",
      url: "/api/content/assets/asset-gif/file",
      associations: [],
    };
    listAssets.mockResolvedValue([gifAsset]);
    listAssetAssociationOptions.mockResolvedValue([]);
    getAdminAssetFile.mockResolvedValue(new Blob(["gif"], { type: "image/gif" }));
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:asset-detail"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Ampliar prévia de Explosão" }));

    expect(await screen.findByText("Quadros")).toBeVisible();
    expect(screen.getByText("200 ms")).toBeVisible();
    expect(screen.getByText("Infinito")).toBeVisible();
    expect(screen.getByText("1: 100 ms · 2: 100 ms")).toBeVisible();
    expect(getAdminAssetFile).toHaveBeenCalledWith("asset-gif");
  });
});
