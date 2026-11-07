import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StoryPage } from "@/components/admin/StoryPage";
import { dataService } from "@/services/dataService";

function renderStoryPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <StoryPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("administrative story page", () => {
  it("explains the empty chapter and scene states without enabling scene creation", async () => {
    vi.spyOn(dataService, "list").mockResolvedValue([]);

    renderStoryPage();

    expect(screen.getByText("Carregando capítulos do servidor…")).toBeVisible();
    expect(
      screen.queryByText("Cadastre um capítulo para começar a estruturar sua história."),
    ).not.toBeInTheDocument();
    expect(await screen.findByText("Nenhum capítulo cadastrado.")).toBeVisible();
    expect(
      screen.getByText("Cadastre um capítulo para começar a estruturar sua história."),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Nova cena" })).toBeDisabled();
  });

  it("shows a server loading error instead of presenting it as empty content", async () => {
    vi.spyOn(dataService, "list").mockRejectedValue(new Error("Falha de rede"));

    renderStoryPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível carregar todo o conteúdo oficial da história ou os modelos de recompensa.",
    );
    expect(await screen.findByText("Erro ao carregar dados.")).toBeVisible();
  });
});
