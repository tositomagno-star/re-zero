import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  getCombatBalanceSettings,
  updateCombatBalanceSettings,
  type CombatBalanceMultipliers,
  type CombatBalancePartyRule,
  type CombatBalanceSettings,
} from "@/lib/combat-balance-api";

const multiplierGroups = [
  { key: "enemies", label: "Inimigos comuns" },
  { key: "bosses", label: "Bosses e minibosses" },
] as const;

const stats = [
  { key: "hp", label: "Vida" },
  { key: "attack", label: "Ataque" },
  { key: "defense", label: "Defesa" },
] as const;

export function CombatBalancePage() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["admin-combat-balance"],
    queryFn: getCombatBalanceSettings,
  });
  const [rules, setRules] = useState<CombatBalancePartyRule[]>([]);

  useEffect(() => {
    if (query.data) setRules(query.data.rules);
  }, [query.data]);

  const save = useMutation({
    mutationFn: updateCombatBalanceSettings,
    onSuccess: (settings) => {
      setRules(settings.rules);
      queryClient.setQueryData(["admin-combat-balance"], settings);
      toast.success("Balanceamento salvo e aplicado às próximas batalhas.");
    },
    onError: (error) => {
      toast.error("Não foi possível salvar o balanceamento.", {
        description: error instanceof Error ? error.message : "Erro inesperado.",
      });
    },
  });

  function updateMultiplier(
    playerCount: number,
    group: (typeof multiplierGroups)[number]["key"],
    stat: keyof CombatBalanceMultipliers,
    percent: number,
  ) {
    if (!Number.isFinite(percent)) return;
    setRules((current) =>
      current.map((rule) =>
        rule.player_count === playerCount
          ? {
              ...rule,
              [group]: { ...rule[group], [stat]: percent / 100 },
            }
          : rule,
      ),
    );
  }

  function resetToDefault() {
    setRules((current) =>
      current.map((rule) => ({
        ...rule,
        enemies: { hp: 1, attack: 1, defense: 1 },
        bosses: { hp: 1, attack: 1, defense: 1 },
      })),
    );
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const settings: CombatBalanceSettings = { rules };
    save.mutate(settings);
  }

  return (
    <div>
      <header className="mb-6">
        <p className="mb-2 text-xs font-medium uppercase tracking-[0.2em] text-primary">
          Regras de combate
        </p>
        <h1 className="font-display text-3xl">Balanceamento por grupo</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          Cada linha corresponde ao número de jogadores ativos quando a batalha começa. Ajuste os
          percentuais de vida, ataque e defesa de inimigos comuns e bosses; 100% mantém o valor
          original. O modo solo usa sempre a regra de 1 jogador.
        </p>
      </header>

      {query.isLoading && <p role="status">Carregando regras de balanceamento...</p>}
      {query.isError && (
        <p className="mb-4 text-sm text-destructive" role="alert">
          Não foi possível carregar as regras:{" "}
          {query.error instanceof Error ? query.error.message : "erro inesperado"}
        </p>
      )}

      {query.data && (
        <form onSubmit={submit} className="space-y-4">
          <div className="overflow-x-auto rounded-xl border">
            <table className="w-full min-w-[780px] border-collapse text-sm">
              <caption className="sr-only">
                Multiplicadores de combate por quantidade de jogadores
              </caption>
              <thead>
                <tr className="bg-muted/50">
                  <th rowSpan={2} scope="col" className="px-4 py-3 text-left">
                    Jogadores
                  </th>
                  {multiplierGroups.map(({ key, label }) => (
                    <th
                      key={key}
                      colSpan={3}
                      scope="colgroup"
                      className="border-l px-3 py-3 text-center"
                    >
                      {label}
                    </th>
                  ))}
                </tr>
                <tr className="bg-muted/30">
                  {multiplierGroups.flatMap(({ key }) =>
                    stats.map(({ key: stat, label }) => (
                      <th
                        key={`${key}-${stat}`}
                        scope="col"
                        className="border-l px-2 py-2 text-center font-medium"
                      >
                        {label} (%)
                      </th>
                    )),
                  )}
                </tr>
              </thead>
              <tbody>
                {rules.map((rule) => (
                  <tr key={rule.player_count} className="border-t">
                    <th scope="row" className="whitespace-nowrap px-4 py-3 text-left font-semibold">
                      {rule.player_count} {rule.player_count === 1 ? "jogador" : "jogadores"}
                    </th>
                    {multiplierGroups.flatMap(({ key, label }) =>
                      stats.map(({ key: stat, label: statLabel }) => {
                        const inputId = `balance-${rule.player_count}-${key}-${stat}`;
                        const value = rule[key][stat];
                        return (
                          <td key={inputId} className="border-l px-2 py-2">
                            <label className="sr-only" htmlFor={inputId}>
                              {rule.player_count}{" "}
                              {rule.player_count === 1 ? "jogador" : "jogadores"} · {label} ·{" "}
                              {statLabel} (%)
                            </label>
                            <Input
                              id={inputId}
                              type="number"
                              min={10}
                              max={500}
                              step={5}
                              required
                              className="mx-auto w-20 text-right"
                              value={Number.isFinite(value) ? Math.round(value * 100) : ""}
                              onChange={(event) =>
                                updateMultiplier(
                                  rule.player_count,
                                  key,
                                  stat,
                                  event.currentTarget.valueAsNumber,
                                )
                              }
                            />
                          </td>
                        );
                      }),
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={save.isPending || rules.length !== 7}>
              {save.isPending ? "Salvando..." : "Salvar balanceamento"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={resetToDefault}
              disabled={save.isPending}
            >
              Voltar tudo para 100%
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
