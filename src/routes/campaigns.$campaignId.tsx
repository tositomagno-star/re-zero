import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { CampaignLobbyPage } from "../components/player/CampaignPages";
import { AuthApiError, getPlayerSession, logoutPlayer, type AuthUser } from "../lib/auth-api";

export const Route = createFileRoute("/campaigns/$campaignId")({
  component: ProtectedCampaignLobby,
});

function ProtectedCampaignLobby() {
  const { campaignId } = Route.useParams();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    void getPlayerSession()
      .then((authenticatedUser) => {
        if (active) {
          setUser(authenticatedUser);
          setLoading(false);
        }
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        if (requestError instanceof AuthApiError && requestError.status === 401) {
          window.location.assign("/login");
        } else {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Não foi possível verificar a sessão.",
          );
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  async function handleLogout() {
    await logoutPlayer();
    window.location.assign("/login");
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center px-5 text-sm text-muted-foreground">
        Verificando sua sessão...
      </main>
    );
  }
  if (error || user === null) {
    return (
      <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center px-5">
        <p
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
        >
          {error || "Não foi possível confirmar a sessão."}
        </p>
        <a className="mt-4 text-sm text-primary hover:underline" href="/login">
          Voltar para o login
        </a>
      </main>
    );
  }
  return <CampaignLobbyPage user={user} campaignId={campaignId} onLogout={handleLogout} />;
}
