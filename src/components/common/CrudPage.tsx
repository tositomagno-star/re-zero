import type { LucideIcon } from "lucide-react";
import {
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Copy,
  Eye,
  Pencil,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCollection, useRemoveEntity, useSaveEntity } from "@/hooks/use-collection";
import { dataService, newId } from "@/services/dataService";
import type { Collection, DemoDB } from "@/types/entities";
import { cleanLists, EntityFormDialog, type FieldDef, type Option } from "./EntityForm";
import { ConfirmDialog, EmptyState, Loading, PageHeader } from "./ui-bits";

type Row = { id: string } & Record<string, unknown>;

export interface Column<T> {
  key: string;
  label: string;
  render?: (row: T) => ReactNode;
  sortValue?: (row: T) => string | number;
  className?: string;
}

interface Props<K extends Collection> {
  collection: K;
  title: string;
  description: string;
  icon: LucideIcon;
  entityLabel: string;
  newEntityLabel?: string;
  columns: Column<DemoDB[K][number]>[];
  fields: FieldDef[];
  defaults: () => Record<string, unknown>;
  searchKeys: string[];
  filter?: { key: string; label: string; options: Option[] };
  validate?: (v: Record<string, unknown>) => string | null;
  formValues?: (entity: DemoDB[K][number]) => Record<string, unknown>;
  prepare?: (values: Record<string, unknown>) => Record<string, unknown>;
  renderDetail?: (row: DemoDB[K][number]) => ReactNode;
  pageSize?: number;
  headerExtra?: ReactNode;
  readOnly?: boolean;
  appendOnly?: boolean;
  allowDuplicate?: boolean;
}

export function CrudPage<K extends Collection>(p: Props<K>) {
  const { data, isLoading, error } = useCollection(p.collection);
  const save = useSaveEntity(p.collection);
  const remove = useRemoveEntity(p.collection);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);
  const [page, setPage] = useState(0);
  const [editing, setEditing] = useState<Row | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [viewing, setViewing] = useState<Row | null>(null);
  const size = p.pageSize ?? 8;
  const isPersistent = dataService.isPersistent(p.collection);

  const rows = useMemo(() => {
    let r = ((data ?? []) as unknown as Row[]).filter(
      (row) =>
        !q ||
        p.searchKeys.some((k) =>
          String(row[k] ?? "")
            .toLowerCase()
            .includes(q.toLowerCase()),
        ),
    );
    if (p.filter && filter !== "all") r = r.filter((row) => String(row[p.filter!.key]) === filter);
    if (sort) {
      const col = p.columns.find((c) => c.key === sort.key);
      const val = (row: Row) =>
        col?.sortValue ? col.sortValue(row as never) : (row[sort.key] as string | number);
      r = [...r].sort((a, b) => (val(a) > val(b) ? 1 : val(a) < val(b) ? -1 : 0) * sort.dir);
    }
    return r;
  }, [data, q, filter, sort, p.searchKeys, p.filter, p.columns]);

  const pages = Math.max(1, Math.ceil(rows.length / size));
  const cur = Math.min(page, pages - 1);
  const visible = rows.slice(cur * size, cur * size + size);

  function openNew() {
    setIsNew(true);
    const defaults = p.defaults();
    setEditing({ id: newId(p.collection), ...defaults } as Row);
  }
  function openEdit(r: Row) {
    setIsNew(false);
    setEditing({ ...r, ...p.formValues?.(r as unknown as DemoDB[K][number]) });
  }
  function openDuplicate(r: Row) {
    setIsNew(true);
    setEditing({
      ...r,
      ...p.formValues?.(r as unknown as DemoDB[K][number]),
      id: newId(p.collection),
    });
  }

  return (
    <div>
      <PageHeader
        title={p.title}
        description={p.description}
        icon={p.icon}
        actions={
          !p.readOnly ? (
            <Button onClick={openNew}>
              <Plus className="h-4 w-4" />
              {p.newEntityLabel ?? `Novo ${p.entityLabel}`}
            </Button>
          ) : undefined
        }
      />
      {p.headerExtra}
      <div className="panel">
        <div className="flex flex-col gap-3 border-b border-border p-4 sm:flex-row">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Pesquisar…"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(0);
              }}
              aria-label="Pesquisar"
            />
          </div>
          {p.filter && (
            <Select
              value={filter}
              onValueChange={(v) => {
                setFilter(v);
                setPage(0);
              }}
            >
              <SelectTrigger className="sm:w-52" aria-label={p.filter.label}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{p.filter.label}: todos</SelectItem>
                {p.filter.options.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
        {isLoading ? (
          <Loading />
        ) : error ? (
          <p className="p-6 text-destructive">Erro ao carregar dados.</p>
        ) : rows.length === 0 ? (
          <div className="p-4">
            <EmptyState
              text={
                q || filter !== "all"
                  ? "Nenhum resultado para os filtros atuais."
                  : `Nenhum ${p.entityLabel} cadastrado.`
              }
            />
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                {p.columns.map((c) => (
                  <TableHead key={c.key} className={c.className}>
                    <button
                      className="inline-flex items-center gap-1 hover:text-foreground"
                      onClick={() =>
                        setSort((s) => ({
                          key: c.key,
                          dir: s?.key === c.key && s.dir === 1 ? -1 : 1,
                        }))
                      }
                    >
                      {c.label}
                      <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </TableHead>
                ))}
                <TableHead className="text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visible.map((r) => (
                <TableRow key={r.id}>
                  {p.columns.map((c) => (
                    <TableCell key={c.key} className={c.className}>
                      {c.render ? c.render(r as never) : String(r[c.key] ?? "")}
                    </TableCell>
                  ))}
                  <TableCell className="text-right whitespace-nowrap">
                    {p.renderDetail && (
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label="Ver detalhes"
                        onClick={() => setViewing(r)}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                    )}
                    {!p.readOnly && !p.appendOnly && (
                      <>
                        {p.allowDuplicate && (
                          <Button
                            size="icon"
                            variant="ghost"
                            aria-label="Duplicar"
                            onClick={() => openDuplicate(r)}
                          >
                            <Copy className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label="Editar"
                          onClick={() => openEdit(r)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <ConfirmDialog
                          title={`Excluir ${p.entityLabel}?`}
                          description={
                            isPersistent
                              ? "A API verificará vínculos com campanhas antes de excluir. Conteúdos referenciados serão desativados."
                              : "Remove o registro apenas dos dados de demonstração deste navegador."
                          }
                          confirmLabel="Excluir"
                          onConfirm={() => remove.mutate(r.id)}
                          trigger={
                            <Button size="icon" variant="ghost" aria-label="Excluir">
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          }
                        />
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        <div className="flex items-center justify-between border-t border-border p-3 text-sm text-muted-foreground">
          <span>{rows.length} registro(s)</span>
          <div className="flex items-center gap-2">
            <Button
              size="icon"
              variant="outline"
              disabled={cur === 0}
              onClick={() => setPage(cur - 1)}
              aria-label="Página anterior"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span>
              {cur + 1} / {pages}
            </span>
            <Button
              size="icon"
              variant="outline"
              disabled={cur >= pages - 1}
              onClick={() => setPage(cur + 1)}
              aria-label="Próxima página"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      <EntityFormDialog
        open={!!editing}
        onOpenChange={(o) => !o && setEditing(null)}
        title={isNew ? (p.newEntityLabel ?? `Novo ${p.entityLabel}`) : `Editar ${p.entityLabel}`}
        fields={p.fields}
        initial={editing ?? {}}
        validate={p.validate}
        description={
          isPersistent
            ? "Este conteúdo oficial será salvo no banco de dados do servidor."
            : "Este registro pertence somente aos dados de demonstração deste navegador."
        }
        submitLabel={isPersistent ? "Salvar no servidor" : "Salvar demonstração"}
        onSubmit={async (v) => {
          const cleaned = cleanLists(v, p.fields);
          await save.mutateAsync((p.prepare?.(cleaned) ?? cleaned) as never);
          setEditing(null);
        }}
      />

      <Sheet open={!!viewing} onOpenChange={(o) => !o && setViewing(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
          <SheetHeader>
            <SheetTitle className="font-display">
              {String(viewing?.["name"] ?? viewing?.["title"] ?? viewing?.["displayName"] ?? "")}
            </SheetTitle>
            <SheetDescription>
              ID estável: <code>{viewing?.id}</code>
            </SheetDescription>
          </SheetHeader>
          <div className="px-4 pb-6">{viewing && p.renderDetail?.(viewing as never)}</div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

export function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="border-b border-border py-2.5">
      <div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-sm">
        {children || <span className="text-muted-foreground">—</span>}
      </div>
    </div>
  );
}

export function Tags({ items }: { items: string[] }) {
  if (!items.length) return <span className="text-muted-foreground">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((t, i) => (
        <span key={i} className="rounded border border-border bg-muted px-1.5 py-0.5 text-xs">
          {t}
        </span>
      ))}
    </div>
  );
}
