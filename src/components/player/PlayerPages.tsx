import { Link, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import {
  ArrowDown,
  ArrowRight,
  BookOpen,
  CircleUserRound,
  Compass,
  Dices,
  Shield,
  Sparkles,
} from "lucide-react";

type AccessMode = "login" | "register";
import { loginPlayer, registerPlayer } from "../../lib/auth-api";

const highlights = [
  {
    icon: BookOpen,
    title: "Crie uma conta de jogador",
    description: "Cadastre-se para acompanhar suas campanhas e seu personagem.",
  },
  {
    icon: Dices,
    title: "Crie ou entre em uma campanha",
    description: "Abra uma sala para seu grupo ou use o código de convite recebido.",
  },
  {
    icon: Compass,
    title: "Decidam os próximos passos juntos",
    description: "Acompanhe as cenas e participe das votações narrativas da campanha.",
  },
];

export function LandingPage() {
  return (
    <main className="min-h-screen overflow-hidden">
      <header className="mx-auto flex w-full max-w-7xl items-center justify-between border-b border-border/50 px-5 py-5 sm:px-8">
        <Link to="/" className="flex items-center gap-3 text-foreground">
          <span className="brand-seal flex size-10 items-center justify-center rounded-xl text-gold">
            <Dices className="size-5" />
          </span>
          <span className="font-display font-semibold tracking-wide">Crônicas do Reino</span>
        </Link>
        <nav aria-label="Acesso à conta" className="flex items-center gap-2 sm:gap-3">
          <Link
            to="/login"
            className="rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Entrar
          </Link>
          <Link
            to="/register"
            className="rounded-lg border border-primary/40 bg-primary/10 px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-primary/20 sm:px-4"
          >
            Criar conta
          </Link>
        </nav>
      </header>

      <section className="relative mx-auto flex min-h-[72vh] max-w-7xl flex-col items-center justify-center px-5 py-20 text-center sm:px-8">
        <div className="magic-wash pointer-events-none absolute inset-0 -z-10" />
        <div className="pointer-events-none absolute left-1/2 top-1/2 -z-10 size-[34rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-magic/10 blur-[120px]" />
        <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-gold/30 bg-gold/10 px-4 py-2 text-xs font-semibold tracking-wide text-gold shadow-sm shadow-gold/5">
          <Sparkles className="size-3.5" />
          RPG multiplayer de fantasia medieval
        </div>
        <h1 className="max-w-4xl text-balance font-serif text-4xl font-semibold leading-tight tracking-tight text-foreground sm:text-6xl lg:text-7xl">
          O destino do reino está{" "}
          <span className="bg-gradient-to-r from-gold via-magic to-gold bg-clip-text text-transparent">
            nas suas mãos
          </span>
        </h1>
        <p className="mt-6 max-w-2xl text-pretty text-base leading-7 text-muted-foreground sm:text-lg">
          Crie uma campanha persistente, convide seu grupo e acompanhe uma aventura de fantasia
          medieval em que as escolhas são feitas em conjunto.
        </p>
        <div className="mt-9 flex w-full flex-col justify-center gap-3 sm:w-auto sm:flex-row">
          <Link
            to="/register"
            className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/15 transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            Criar minha conta
            <ArrowRight className="size-4" />
          </Link>
          <Link
            to="/play"
            className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-border/80 bg-card/80 px-6 py-3 text-sm font-medium text-foreground transition-colors hover:border-primary/40 hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            Acessar campanhas
          </Link>
        </div>
        <a
          href="#aventura"
          className="mt-14 inline-flex items-center gap-2 text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          Conheça a plataforma
          <ArrowDown className="size-3.5" />
        </a>
      </section>

      <section
        id="aventura"
        aria-labelledby="adventure-heading"
        className="mx-auto max-w-7xl px-5 pb-20 sm:px-8"
      >
        <div className="mb-7 max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
            Como funciona
          </p>
          <h2
            id="adventure-heading"
            className="mt-2 font-serif text-2xl font-semibold text-foreground sm:text-3xl"
          >
            Sua aventura começa com o grupo
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Faça seu cadastro, reúna os participantes em uma sala e acompanhe a narrativa campanha
            após campanha.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {highlights.map(({ icon: Icon, title, description }, index) => (
            <article key={title} className="fantasy-card rounded-2xl border p-6 transition-colors">
              <span className="mb-5 flex size-11 items-center justify-center rounded-xl border border-magic/20 bg-magic/10 text-magic">
                <Icon className="size-5" />
              </span>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">
                Passo {index + 1}
              </p>
              <h3 className="mt-2 text-lg font-semibold text-foreground">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
            </article>
          ))}
        </div>
        <p className="mt-6 text-sm text-muted-foreground">
          Já tem uma conta?{" "}
          <Link to="/login" className="font-medium text-primary underline-offset-4 hover:underline">
            Entre para continuar
          </Link>{" "}
          ou{" "}
          <Link to="/play" className="font-medium text-primary underline-offset-4 hover:underline">
            abra sua área de campanhas
          </Link>
          .
        </p>
      </section>

      <footer className="border-t border-border/70 bg-background/35">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-5 py-6 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <span>Crônicas do Reino · Uma plataforma de RPG em construção</span>
          <Link
            to="/admin/login"
            className="inline-flex items-center gap-2 transition-colors hover:text-foreground"
          >
            <Shield className="size-3.5" />
            Acesso administrativo
          </Link>
        </div>
      </footer>
    </main>
  );
}

export function AccessPlaceholder({ mode }: { mode: AccessMode }) {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isLogin = mode === "login";
  const usernameHint = "De 3 a 32 caracteres: letras, números ou sublinhado.";
  const passwordHint = isLogin
    ? "Informe a senha cadastrada. Contas existentes continuam podendo entrar."
    : "Use pelo menos 12 caracteres. A senha é protegida antes de ser armazenada.";

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

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (!isLogin && password !== confirmation) {
      setError("As senhas não conferem.");
      return;
    }
    setBusy(true);
    try {
      if (isLogin) await loginPlayer(username, password);
      else await registerPlayer(username, password);
      await navigate({ to: "/play" });
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível concluir a solicitação.",
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
          <CircleUserRound className="size-6" />
        </span>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
          {isLogin ? "Já tem uma conta?" : "Primeiro passo"}
        </p>
        <h1 className="mt-3 font-serif text-3xl font-semibold text-foreground">
          {isLogin ? "Entrar" : "Criar conta de jogador"}
        </h1>
        <p className="mt-4 leading-7 text-muted-foreground">
          {isLogin
            ? "Acesse suas campanhas com o nome de usuário e a senha cadastrados."
            : "Crie seu acesso para participar de campanhas. Você poderá criar uma sala ou entrar com um código de convite."}
        </p>
        <form className="mt-7 space-y-4" onSubmit={(event) => void submit(event)}>
          <label className="block space-y-2 text-sm font-medium" htmlFor="player-username">
            Nome de usuário
            <input
              id="player-username"
              autoComplete="username"
              className="auth-field w-full rounded-lg border px-3 py-2.5 text-foreground outline-none transition focus-visible:ring-2 focus-visible:ring-ring"
              value={username}
              onChange={(event) => {
                event.currentTarget.setCustomValidity("");
                setUsername(event.target.value);
              }}
              minLength={3}
              maxLength={32}
              pattern="[A-Za-z0-9_]{3,32}"
              aria-describedby="player-username-hint"
              onInvalid={(event) => setPortugueseValidity(event.currentTarget)}
              required
            />
            <span
              id="player-username-hint"
              className="block text-xs font-normal text-muted-foreground"
            >
              {usernameHint}
            </span>
          </label>
          <label className="block space-y-2 text-sm font-medium" htmlFor="player-password">
            Senha
            <input
              id="player-password"
              type="password"
              autoComplete={isLogin ? "current-password" : "new-password"}
              className="auth-field w-full rounded-lg border px-3 py-2.5 text-foreground outline-none transition focus-visible:ring-2 focus-visible:ring-ring"
              value={password}
              onChange={(event) => {
                event.currentTarget.setCustomValidity("");
                setPassword(event.target.value);
              }}
              minLength={isLogin ? undefined : 12}
              maxLength={128}
              aria-describedby="player-password-hint"
              onInvalid={(event) => setPortugueseValidity(event.currentTarget)}
              required
            />
            <span
              id="player-password-hint"
              className="block text-xs font-normal text-muted-foreground"
            >
              {passwordHint}
            </span>
          </label>
          {!isLogin && (
            <label
              className="block space-y-2 text-sm font-medium"
              htmlFor="player-password-confirm"
            >
              Confirme a senha
              <input
                id="player-password-confirm"
                type="password"
                autoComplete="new-password"
                className="auth-field w-full rounded-lg border px-3 py-2.5 text-foreground outline-none transition focus-visible:ring-2 focus-visible:ring-ring"
                value={confirmation}
                onChange={(event) => {
                  event.currentTarget.setCustomValidity("");
                  setConfirmation(event.target.value);
                }}
                minLength={12}
                maxLength={128}
                onInvalid={(event) => setPortugueseValidity(event.currentTarget)}
                required
              />
            </label>
          )}
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
            {busy ? "Aguarde..." : isLogin ? "Entrar" : "Criar conta"}
          </button>
          {busy && (
            <p
              role="status"
              aria-live="polite"
              className="text-center text-sm text-muted-foreground"
            >
              {isLogin ? "Verificando seus dados..." : "Criando sua conta..."}
            </p>
          )}
        </form>
        <div className="mt-5 flex flex-wrap gap-x-4 gap-y-2 text-sm">
          <Link className="text-primary hover:underline" to={isLogin ? "/register" : "/login"}>
            {isLogin ? "Criar uma conta" : "Já tenho conta: entrar"}
          </Link>
          {isLogin && (
            <Link className="text-muted-foreground hover:text-foreground" to="/admin/login">
              Acesso administrativo
            </Link>
          )}
        </div>
      </section>
    </main>
  );
}
