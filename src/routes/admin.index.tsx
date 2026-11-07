import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { AdminApp } from "../components/admin/AdminApp";
import { AuthApiError, getAdminSession, logoutAdmin } from "../lib/auth-api";

export const Route = createFileRoute("/admin/")({
  component: ProtectedAdminArea,
});

function ProtectedAdminArea() {
  const [authorized, setAuthorized] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    void getAdminSession()
      .then(() => {
        if (active) setAuthorized(true);
      })
      .catch((requestError: unknown) => {
        if (!active) return;
        if (requestError instanceof AuthApiError && requestError.status === 401) {
          window.location.assign("/admin/login");
        } else {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Não foi possível verificar o acesso administrativo.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, [retry]);

  async function handleLogout() {
    await logoutAdmin();
    window.location.assign("/admin/login");
  }

  if (authorized) return <AdminApp onLogout={handleLogout} />;

  return (
    <main className="flex min-h-screen items-center justify-center px-5">
      <div className="max-w-md text-center">
        {error ? (
          <>
            <h1 className="text-xl font-semibold text-foreground">
              Não foi possível verificar o acesso
            </h1>
            <p role="alert" className="mt-3 text-sm text-muted-foreground">
              {error}
            </p>
            <button
              type="button"
              onClick={() => {
                setError("");
                setRetry((value) => value + 1);
              }}
              className="mt-5 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground"
            >
              Tentar novamente
            </button>
            <p className="mt-4">
              <a className="text-sm text-primary hover:underline" href="/admin/login">
                Entrar como administrador
              </a>
            </p>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Verificando acesso administrativo...</p>
        )}
      </div>
    </main>
  );
}
