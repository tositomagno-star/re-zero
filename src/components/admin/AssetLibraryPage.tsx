import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Eye,
  FileImage,
  ImagePlus,
  Link2,
  Pencil,
  Plus,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { ConfirmDialog, EmptyState, PageHeader } from "@/components/common/ui-bits";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  createAsset,
  deleteAsset,
  getAdminAssetFile,
  listAssetAssociationOptions,
  listAssets,
  replaceAssetFile,
  updateAssetMetadata,
  type AssetCategory,
  type AssetEntityType,
  type AssetMetadata,
  type AssetRecord,
} from "@/lib/admin-content-api";

const categories: { value: AssetCategory; label: string }[] = [
  { value: "characters", label: "Personagens" },
  { value: "npcs", label: "NPCs" },
  { value: "allies", label: "Aliados" },
  { value: "hostiles", label: "Hostis" },
  { value: "monsters", label: "Monstros" },
  { value: "minibosses", label: "Minibosses" },
  { value: "bosses", label: "Bosses" },
  { value: "weapons", label: "Armas" },
  { value: "equipment", label: "Equipamentos" },
  { value: "spells", label: "Magias" },
  { value: "powers", label: "Poderes" },
  { value: "visual_effects", label: "Efeitos visuais" },
];

const entityTypes: { value: AssetEntityType; label: string }[] = [
  { value: "character", label: "Personagem" },
  { value: "npc", label: "NPC" },
  { value: "enemy", label: "Monstro" },
  { value: "item", label: "Item" },
  { value: "skill", label: "Magia ou habilidade" },
];

function isAssetCategory(value: string): value is AssetCategory {
  return categories.some((category) => category.value === value);
}

function isAssetEntityType(value: string): value is AssetEntityType {
  return entityTypes.some((type) => type.value === value);
}

const EMPTY_METADATA: AssetMetadata = {
  name: "",
  description: "",
  category: "characters",
  subcategory: null,
  asset_type: null,
  is_public: false,
  associations: [],
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function AdminAssetImage({
  asset,
  alt,
  className,
}: {
  asset: AssetRecord;
  alt: string;
  className: string;
}) {
  const fileQuery = useQuery({
    queryKey: ["admin-assets", "file", asset.id, asset.updated_at],
    queryFn: () => getAdminAssetFile(asset.id),
    staleTime: 0,
    gcTime: 0,
    retry: false,
  });
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    if (!fileQuery.data) {
      setSrc(null);
      return;
    }
    const objectUrl = URL.createObjectURL(fileQuery.data);
    setSrc(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [fileQuery.data]);

  if (!src) {
    return (
      <div
        className={`${className} flex items-center justify-center bg-muted text-xs text-muted-foreground`}
        role="img"
        aria-label={alt}
      >
        {fileQuery.isError ? "Prévia indisponível" : "Carregando prévia…"}
      </div>
    );
  }
  return <img src={src} alt={alt} className={className} />;
}

function AssetEditorDialog({
  asset,
  open,
  onOpenChange,
}: {
  asset: AssetRecord | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [metadata, setMetadata] = useState<AssetMetadata>(
    asset
      ? {
          name: asset.name,
          description: asset.description,
          category: asset.category,
          subcategory: asset.subcategory,
          asset_type: asset.asset_type,
          is_public: asset.is_public,
          associations: asset.associations.map(({ entity_type, entity_id }) => ({
            entity_type,
            entity_id,
          })),
        }
      : EMPTY_METADATA,
  );
  const [file, setFile] = useState<File | null>(null);
  const [entityType, setEntityType] = useState<AssetEntityType>("character");
  const [entityId, setEntityId] = useState("");
  const optionsQuery = useQuery({
    queryKey: ["admin-assets", "association-options"],
    queryFn: listAssetAssociationOptions,
    staleTime: 30_000,
  });
  const options = optionsQuery.data ?? [];
  const matchingOptions = options.filter((option) => option.entity_type === entityType);
  const selectedOption = matchingOptions.find((option) => option.entity_id === entityId);
  const objectUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);

  useEffect(() => {
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [objectUrl]);

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!metadata.name.trim()) throw new Error("Informe o nome do asset.");
      if (!asset && !file) throw new Error("Selecione uma imagem para cadastrar.");
      if (asset) return updateAssetMetadata(asset.id, metadata);
      if (!file) throw new Error("Selecione uma imagem para cadastrar.");
      return createAsset(file, metadata);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-assets"] });
      toast.success(asset ? "Metadados atualizados." : "Asset cadastrado.");
      onOpenChange(false);
    },
    onError: (error) =>
      toast.error("Não foi possível salvar o asset.", {
        description: error instanceof Error ? error.message : String(error),
      }),
  });
  const replaceMutation = useMutation({
    mutationFn: () => {
      if (!asset || !file) throw new Error("Selecione o novo arquivo.");
      return replaceAssetFile(asset.id, file);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-assets"] });
      toast.success("Arquivo substituído; identificador e vínculos foram mantidos.");
      onOpenChange(false);
    },
    onError: (error) =>
      toast.error("Não foi possível substituir o arquivo.", {
        description: error instanceof Error ? error.message : String(error),
      }),
  });

  function addAssociation() {
    if (!selectedOption) return;
    const alreadyAdded = metadata.associations.some(
      (item) => item.entity_type === entityType && item.entity_id === entityId,
    );
    if (alreadyAdded) {
      toast.error("Essa entidade já está vinculada.");
      return;
    }
    setMetadata((current) => ({
      ...current,
      associations: [...current.associations, { entity_type: entityType, entity_id: entityId }],
    }));
    setEntityId("");
  }

  function displayAssociation(entityTypeValue: AssetEntityType, id: string): string {
    const fromOptions = options.find(
      (option) => option.entity_type === entityTypeValue && option.entity_id === id,
    );
    const fromAsset = asset?.associations.find(
      (item) => item.entity_type === entityTypeValue && item.entity_id === id,
    );
    const typeLabel = entityTypes.find((item) => item.value === entityTypeValue)?.label;
    return `${typeLabel}: ${fromOptions?.entity_name ?? fromAsset?.entity_name ?? id}`;
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{asset ? "Editar asset" : "Cadastrar asset"}</DialogTitle>
          <DialogDescription>
            Imagens PNG, JPG, JPEG, WebP ou GIF. O servidor pode configurar um limite menor que 5
            MB.
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-5"
          onSubmit={(event) => {
            event.preventDefault();
            saveMutation.mutate();
          }}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-1.5 text-sm">
              <span>Nome</span>
              <Input
                required
                maxLength={160}
                value={metadata.name}
                onChange={(event) =>
                  setMetadata((current) => ({ ...current, name: event.target.value }))
                }
              />
            </label>
            <label className="space-y-1.5 text-sm">
              <span>Categoria</span>
              <select
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={metadata.category}
                onChange={(event) => {
                  const selectedCategory = event.target.value;
                  if (isAssetCategory(selectedCategory)) {
                    setMetadata((current) => ({
                      ...current,
                      category: selectedCategory,
                    }));
                  }
                }}
              >
                {categories.map((category) => (
                  <option key={category.value} value={category.value}>
                    {category.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1.5 text-sm">
              <span>Subcategoria (opcional)</span>
              <Input
                maxLength={80}
                value={metadata.subcategory ?? ""}
                placeholder="Ex.: arqueiros, chefes de fase"
                onChange={(event) =>
                  setMetadata((current) => ({
                    ...current,
                    subcategory: event.target.value || null,
                  }))
                }
              />
            </label>
            <label className="space-y-1.5 text-sm">
              <span>Tipo específico (opcional)</span>
              <Input
                maxLength={80}
                value={metadata.asset_type ?? ""}
                placeholder="Ex.: idle, ataque, impacto"
                onChange={(event) =>
                  setMetadata((current) => ({
                    ...current,
                    asset_type: event.target.value || null,
                  }))
                }
              />
            </label>
          </div>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={metadata.is_public}
              onChange={(event) =>
                setMetadata((current) => ({ ...current, is_public: event.target.checked }))
              }
            />
            <span>
              Disponibilizar arquivo publicamente para o jogo
              <span className="mt-0.5 block text-xs text-muted-foreground">
                Desmarcado: somente administradores autenticados podem visualizar o arquivo.
              </span>
            </span>
          </label>
          <label className="block space-y-1.5 text-sm">
            <span>Descrição</span>
            <Textarea
              maxLength={20000}
              rows={3}
              value={metadata.description}
              onChange={(event) =>
                setMetadata((current) => ({ ...current, description: event.target.value }))
              }
            />
          </label>

          <section className="space-y-3 rounded-lg border border-border p-3">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Link2 className="h-4 w-4 text-primary" />
              Associações com entidades
            </div>
            <div className="grid gap-2 sm:grid-cols-[1fr_1.5fr_auto]">
              <select
                aria-label="Tipo de entidade"
                className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                value={entityType}
                onChange={(event) => {
                  if (isAssetEntityType(event.target.value)) {
                    setEntityType(event.target.value);
                    setEntityId("");
                  }
                }}
              >
                {entityTypes.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
              <select
                aria-label="Entidade"
                className="h-10 min-w-0 rounded-md border border-input bg-background px-3 text-sm"
                value={entityId}
                onChange={(event) => setEntityId(event.target.value)}
                disabled={optionsQuery.isLoading || matchingOptions.length === 0}
              >
                <option value="">
                  {optionsQuery.isLoading ? "Carregando…" : "Selecione uma entidade"}
                </option>
                {matchingOptions.map((option) => (
                  <option key={option.entity_id} value={option.entity_id}>
                    {option.entity_name}
                  </option>
                ))}
              </select>
              <Button
                type="button"
                variant="outline"
                onClick={addAssociation}
                disabled={!selectedOption}
              >
                <Plus className="mr-1 h-4 w-4" />
                Vincular
              </Button>
            </div>
            {optionsQuery.isError && (
              <p className="text-sm text-destructive">
                Não foi possível carregar as entidades para vínculo.
              </p>
            )}
            {metadata.associations.length > 0 && (
              <ul className="space-y-2">
                {metadata.associations.map((association) => (
                  <li
                    key={`${association.entity_type}:${association.entity_id}`}
                    className="flex items-center justify-between gap-3 rounded-md bg-muted/50 px-3 py-2 text-sm"
                  >
                    <span className="min-w-0 truncate">
                      {displayAssociation(association.entity_type, association.entity_id)}
                    </span>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      aria-label="Remover vínculo"
                      onClick={() =>
                        setMetadata((current) => ({
                          ...current,
                          associations: current.associations.filter(
                            (item) =>
                              item.entity_type !== association.entity_type ||
                              item.entity_id !== association.entity_id,
                          ),
                        }))
                      }
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="space-y-3 rounded-lg border border-border p-3">
            <label className="block space-y-2 text-sm">
              <span>{asset ? "Substituir arquivo (opcional)" : "Arquivo de imagem"}</span>
              <Input
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif"
                required={!asset}
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </label>
            {(objectUrl || asset) && (
              <div className="flex items-center gap-3">
                {objectUrl || asset ? (
                  objectUrl ? (
                    <img
                      src={objectUrl}
                      alt={file?.name ?? "Prévia do arquivo selecionado"}
                      className="h-24 w-24 rounded-md border border-border bg-muted object-contain"
                    />
                  ) : asset ? (
                    <AdminAssetImage
                      asset={asset}
                      alt={asset.name}
                      className="h-24 w-24 rounded-md border border-border object-contain"
                    />
                  ) : null
                ) : null}
                <div className="min-w-0 text-xs text-muted-foreground">
                  <p className="truncate">{file?.name ?? asset?.original_filename}</p>
                  {file ? (
                    <p>{formatBytes(file.size)}</p>
                  ) : (
                    <p>
                      {asset?.width} × {asset?.height} px · {formatBytes(asset?.size_bytes ?? 0)}
                    </p>
                  )}
                  {!asset && <p>A prévia é local e ainda não foi enviada.</p>}
                  {asset && file && (
                    <p>A substituição é enviada apenas ao confirmar o botão abaixo.</p>
                  )}
                </div>
              </div>
            )}
          </section>

          {asset && (
            <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
              <ConfirmDialog
                trigger={
                  <Button
                    type="button"
                    variant="outline"
                    disabled={!file || replaceMutation.isPending}
                  >
                    <Upload className="mr-2 h-4 w-4" />
                    Substituir arquivo
                  </Button>
                }
                title="Substituir arquivo?"
                description="O arquivo será validado e armazenado com um nome novo. O identificador e os vínculos do asset serão preservados."
                confirmLabel={
                  replaceMutation.isPending ? "Substituindo…" : "Confirmar substituição"
                }
                onConfirm={() => replaceMutation.mutate()}
              />
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={saveMutation.isPending}>
              {saveMutation.isPending ? "Salvando…" : asset ? "Salvar metadados" : "Cadastrar"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function AssetLibraryPage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<AssetCategory | "">("");
  const [editor, setEditor] = useState<{ asset: AssetRecord | null; key: number } | null>(null);
  const [preview, setPreview] = useState<AssetRecord | null>(null);
  const queryClient = useQueryClient();
  const assetsQuery = useQuery({
    queryKey: ["admin-assets", category, search],
    queryFn: () => listAssets(category, search),
    staleTime: 15_000,
  });
  const removeMutation = useMutation({
    mutationFn: deleteAsset,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-assets"] });
      toast.success("Asset excluído.");
    },
    onError: (error) =>
      toast.error("Não foi possível excluir o asset.", {
        description: error instanceof Error ? error.message : String(error),
      }),
  });
  const assets = assetsQuery.data ?? [];

  return (
    <div>
      <PageHeader
        title="Biblioteca de Assets"
        description="Imagens e arquivos visuais usados pelo conteúdo do jogo."
        icon={FileImage}
        actions={
          <Button onClick={() => setEditor({ asset: null, key: Date.now() })}>
            <ImagePlus className="mr-2 h-4 w-4" />
            Novo asset
          </Button>
        }
      />

      <div className="mb-5 grid gap-3 sm:grid-cols-[minmax(0,1fr)_240px]">
        <label className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Pesquisar pelo nome…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <select
          aria-label="Filtrar por categoria"
          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          value={category}
          onChange={(event) => {
            if (event.target.value === "" || isAssetCategory(event.target.value)) {
              setCategory(event.target.value);
            }
          }}
        >
          <option value="">Todas as categorias</option>
          {categories.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      </div>

      {assetsQuery.isLoading ? (
        <p className="py-10 text-center text-sm text-muted-foreground">Carregando assets…</p>
      ) : assetsQuery.isError ? (
        <Card>
          <CardContent className="p-6 text-sm text-destructive">
            Não foi possível carregar a biblioteca:{" "}
            {assetsQuery.error instanceof Error ? assetsQuery.error.message : "erro inesperado"}
          </CardContent>
        </Card>
      ) : assets.length === 0 ? (
        <EmptyState
          title={search || category ? "Nenhum resultado" : "Biblioteca vazia"}
          text={
            search || category
              ? "Altere a pesquisa ou o filtro para encontrar outro asset."
              : "Cadastre uma imagem para começar a biblioteca."
          }
          action={
            !search && !category ? (
              <Button onClick={() => setEditor({ asset: null, key: Date.now() })}>
                <Plus className="mr-2 h-4 w-4" />
                Cadastrar primeiro asset
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {assets.map((asset) => {
            const categoryLabel =
              categories.find((item) => item.value === asset.category)?.label ?? asset.category;
            return (
              <Card key={asset.id} className="overflow-hidden">
                <button
                  type="button"
                  className="group relative block h-48 w-full bg-muted/50"
                  aria-label={`Ampliar prévia de ${asset.name}`}
                  onClick={() => setPreview(asset)}
                >
                  <AdminAssetImage
                    asset={asset}
                    alt={asset.name}
                    className="h-full w-full object-contain p-2"
                  />
                  <span className="absolute inset-0 flex items-center justify-center bg-black/0 text-white opacity-0 transition group-hover:bg-black/35 group-hover:opacity-100">
                    <Eye className="h-6 w-6" />
                  </span>
                </button>
                <CardContent className="space-y-3 p-4">
                  <div className="min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <h2 className="truncate font-medium">{asset.name}</h2>
                      <div className="flex shrink-0 gap-1">
                        <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">
                          {categoryLabel}
                        </span>
                        <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                          {asset.is_public ? "Público" : "Privado"}
                        </span>
                        <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                          {asset.is_in_use ? "Em uso" : "Sem vínculos"}
                        </span>
                      </div>
                    </div>
                    {asset.description && (
                      <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                        {asset.description}
                      </p>
                    )}
                    {(asset.subcategory || asset.asset_type) && (
                      <p className="truncate text-xs text-muted-foreground">
                        {[asset.subcategory, asset.asset_type].filter(Boolean).join(" · ")}
                      </p>
                    )}
                  </div>
                  <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    <dt>Formato</dt>
                    <dd className="text-right">{asset.content_type}</dd>
                    <dt>Dimensões</dt>
                    <dd className="text-right">
                      {asset.width} × {asset.height} px
                    </dd>
                    <dt>Tamanho</dt>
                    <dd className="text-right">{formatBytes(asset.size_bytes)}</dd>
                    <dt>Cadastrado</dt>
                    <dd className="text-right">{formatDate(asset.created_at)}</dd>
                    <dt>Atualizado</dt>
                    <dd className="text-right">{formatDate(asset.updated_at)}</dd>
                  </dl>
                  {asset.associations.length > 0 && (
                    <p className="truncate text-xs text-muted-foreground">
                      <Link2 className="mr-1 inline h-3 w-3" />
                      {asset.associations.map((item) => item.entity_name).join(", ")}
                    </p>
                  )}
                  <div className="flex justify-end gap-2 border-t border-border pt-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setEditor({ asset, key: Date.now() })}
                    >
                      <Pencil className="mr-1.5 h-3.5 w-3.5" />
                      Editar
                    </Button>
                    <ConfirmDialog
                      trigger={
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-destructive hover:text-destructive"
                          disabled={removeMutation.isPending}
                        >
                          <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                          Excluir
                        </Button>
                      }
                      title="Excluir asset?"
                      description={
                        asset.associations.length
                          ? `Este asset tem ${asset.associations.length} vínculo(s). Remova os vínculos antes de excluir.`
                          : "A exclusão só será concluída se nenhum conteúdo do jogo ainda referenciar este arquivo."
                      }
                      confirmLabel="Excluir asset"
                      onConfirm={() => removeMutation.mutate(asset.id)}
                    />
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {editor && (
        <AssetEditorDialog
          key={editor.key}
          asset={editor.asset}
          open
          onOpenChange={(open) => {
            if (!open) setEditor(null);
          }}
        />
      )}
      <Dialog open={preview !== null} onOpenChange={(open) => !open && setPreview(null)}>
        <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-4xl">
          {preview && (
            <>
              <DialogHeader>
                <DialogTitle>{preview.name}</DialogTitle>
                <DialogDescription>
                  {preview.description || "Prévia do arquivo original."}
                </DialogDescription>
              </DialogHeader>
              <div className="flex max-h-[65vh] items-center justify-center overflow-hidden rounded-lg bg-muted/50 p-3">
                <AdminAssetImage
                  asset={preview}
                  alt={preview.name}
                  className="max-h-[60vh] max-w-full object-contain"
                />
              </div>
              <p className="text-sm text-muted-foreground">
                {preview.original_filename} · {preview.content_type} · {preview.width} ×{" "}
                {preview.height} px · {formatBytes(preview.size_bytes)}
              </p>
              <p className="text-sm text-muted-foreground">
                Acesso: {preview.is_public ? "público para o jogo" : "somente administrador"}
              </p>
              <dl className="grid gap-2 text-sm sm:grid-cols-2">
                <dt className="text-muted-foreground">Proporção</dt>
                <dd>
                  {preview.analysis_metadata.aspect_ratio === null
                    ? "Não informada"
                    : preview.analysis_metadata.aspect_ratio}
                </dd>
                <dt className="text-muted-foreground">Transparência</dt>
                <dd>
                  {preview.analysis_metadata.has_transparency === null
                    ? "Não informada"
                    : preview.analysis_metadata.has_transparency
                      ? "Presente"
                      : "Ausente"}
                </dd>
                {preview.analysis_metadata.gif && (
                  <>
                    <dt className="text-muted-foreground">Quadros</dt>
                    <dd>{preview.analysis_metadata.gif.frame_count}</dd>
                    <dt className="text-muted-foreground">Duração total</dt>
                    <dd>
                      {preview.analysis_metadata.gif.total_duration_ms === null
                        ? "Desconhecida"
                        : `${preview.analysis_metadata.gif.total_duration_ms} ms`}
                    </dd>
                    <dt className="text-muted-foreground">Loop</dt>
                    <dd>
                      {preview.analysis_metadata.gif.loop === null
                        ? "Não informado"
                        : preview.analysis_metadata.gif.loop === 0
                          ? "Infinito"
                          : `${preview.analysis_metadata.gif.loop} repetições`}
                    </dd>
                    <dt className="text-muted-foreground">Duração por quadro</dt>
                    <dd className="break-words">
                      {preview.analysis_metadata.gif.frame_durations_ms
                        .map((duration, index) =>
                          duration === null
                            ? `${index + 1}: desconhecida`
                            : `${index + 1}: ${duration} ms`,
                        )
                        .join(" · ")}
                    </dd>
                  </>
                )}
              </dl>
              <p className="break-all font-mono text-xs text-muted-foreground">
                Identificador: {preview.id}
              </p>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
