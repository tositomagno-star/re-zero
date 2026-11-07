import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { dataService } from "@/services/dataService";
import type { Collection, DemoDB } from "@/types/entities";

export function useCollection<K extends Collection>(c: K) {
  return useQuery({ queryKey: ["admin-content", c], queryFn: () => dataService.list(c) });
}

export function useSaveEntity<K extends Collection>(c: K) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (e: DemoDB[K][number]) => dataService.save(c, e),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-content", c] });
      if (dataService.isPersistent(c)) {
        toast.success("Conteúdo oficial salvo no servidor.");
      } else {
        toast.success("Salvo localmente (demonstração)", {
          description: "Nada foi enviado ao servidor.",
        });
      }
    },
    onError: (err) => toast.error("Falha ao salvar", { description: String(err) }),
  });
}

export function useRemoveEntity<K extends Collection>(c: K) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => dataService.remove(c, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-content", c] });
      toast.success(
        dataService.isPersistent(c)
          ? "Conteúdo atualizado no servidor."
          : "Removido localmente (demonstração)",
      );
    },
    onError: (err) => toast.error("Falha ao remover", { description: String(err) }),
  });
}
