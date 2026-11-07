import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { Shield } from "lucide-react";

import { loginAdmin } from "../../lib/auth-api";

function setPortugueseValidity(input: HTMLInputElement) {
  if (input.validity.valueMissing) input.setCustomValidity("Este campo é obrigatório.");
  else if (input.validity.tooShort)
    input.setCustomValidity(`Use pelo menos ${input.minLength} caracteres.`);
  else if (input.validity.tooLong)
    input.setCustomValidity(`Use no máximo ${input.maxLength} caracteres.`);
  else if (input.validity.patternMismatch)
    input.setCustomValidity("Use de 3 a 32 letras, números ou sublinhados.");
  else input.setCustomValidity("Confira o valor informado.");
}

export function AdminLoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await loginAdmin(username, password);
      await navigate({ to: "/admin", replace: true });
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível autenticar a administração.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center px-5 py-16">
      <Link to="/" className="mb-8 text-sm text-muted-foreground hover:text-foreground">
        ← Voltar ao início
      </Link>
      <section className="fantasy-card rounded-2xl border p-6 sm:p-9">
        <span className="brand-seal mb-5 flex size-12 items-center justify-center rounded-xl text-gold">
          <Shield className="size-6" />
        </span>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gold">
          Acesso restrito
        </p>
        <h1 className="mt-3 font-serif text-3xl font-semibold text-foreground">Administração</h1>
        <p className="mt-4 leading-7 text-muted-foreground">
          Entre com o nome de usuário (não o e-mail) e a senha da conta administrativa criada para
          este ambiente. Contas de jogadores não têm acesso ao painel do mestre.
        </p>
        <form className="mt-7 space-y-4" onSubmit={(event) => void submit(event)}>
          <label className="block space-y-2 text-sm font-medium" htmlFor="admin-username">
            Nome de usuário administrativo
            <input
              id="admin-username"
              autoComplete="username"
              className="auth-field w-full rounded-lg border px-3 py-2.5 text-foreground outline-none transition focus-visible:ring-2 focus-visible:ring-ring"
              value={username}
              onChange={(event) => {
                event.currentTarget.setCustomValidity("");
                setUsername(event.target.value);
              }}
              type="text"
              minLength={3}
              maxLength={32}
              pattern="[A-Za-z0-9_]{3,32}"
              onInvalid={(event) => setPortugueseValidity(event.currentTarget)}
              required
            />
          </label>
          <label className="block space-y-2 text-sm font-medium" htmlFor="admin-password">
            Senha administrativa (mínimo 12 caracteres)
            <input
              id="admin-password"
              type="password"
              autoComplete="current-password"
              className="auth-field w-full rounded-lg border px-3 py-2.5 text-foreground outline-none transition focus-visible:ring-2 focus-visible:ring-ring"
              value={password}
              onChange={(event) => {
                event.currentTarget.setCustomValidity("");
                setPassword(event.target.value);
              }}
              minLength={12}
              maxLength={128}
              onInvalid={(event) => setPortugueseValidity(event.currentTarget)}
              required
            />
          </label>
          {error && (
            <p
              role="alert"
              className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
            >
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={busy}
            aria-busy={busy}
            className="min-h-11 w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-md shadow-primary/10 transition-opacity hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-wait disabled:opacity-60"
          >
            {busy ? "Verificando..." : "Entrar no painel"}
          </button>
          {busy && (
            <p
              role="status"
              aria-live="polite"
              className="text-center text-sm text-muted-foreground"
            >
              Verificando o acesso administrativo...
            </p>
          )}
        </form>
      </section>
    </main>
  );
}
