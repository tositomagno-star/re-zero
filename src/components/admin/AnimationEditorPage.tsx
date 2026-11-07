import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { decompressFrames, parseGIF, type ParsedFrame } from "gifuct-js";
import { ArrowRight, Clapperboard, Copy, Play, Plus, Save, Square, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { ConfirmDialog, EmptyState, PageHeader } from "@/components/common/ui-bits";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  deleteAnimationConfiguration,
  getAdminAssetFile,
  listAssetAssociationOptions,
  listAssets,
  listAnimationConfigurations,
  saveAnimationConfiguration,
  type AnimationConfigurationRecord,
  type AnimationConfigurationWrite,
  type AnimationTrajectory,
  type AssetAssociationOption,
  type AssetRecord,
  type NormalizedPoint,
} from "@/lib/admin-content-api";

const trajectories: { value: AnimationTrajectory; label: string }[] = [
  { value: "right_to_center", label: "Direita para centro" },
  { value: "left_to_center", label: "Esquerda para centro" },
  { value: "right_to_left", label: "Direita para esquerda" },
  { value: "left_to_right", label: "Esquerda para direita" },
  { value: "bottom_to_top", label: "Baixo para cima" },
  { value: "top_to_bottom", label: "Cima para baixo" },
  { value: "origin_to_target", label: "Origem até alvo" },
  { value: "direct_impact", label: "Impacto direto" },
  { value: "area_effect", label: "Área de efeito" },
];

const trajectoryPoints: Partial<Record<AnimationTrajectory, [NormalizedPoint, NormalizedPoint]>> = {
  right_to_center: [
    { x: 0.95, y: 0.5 },
    { x: 0.5, y: 0.5 },
  ],
  left_to_center: [
    { x: 0.05, y: 0.5 },
    { x: 0.5, y: 0.5 },
  ],
  right_to_left: [
    { x: 0.95, y: 0.5 },
    { x: 0.05, y: 0.5 },
  ],
  left_to_right: [
    { x: 0.05, y: 0.5 },
    { x: 0.95, y: 0.5 },
  ],
  bottom_to_top: [
    { x: 0.5, y: 0.95 },
    { x: 0.5, y: 0.05 },
  ],
  top_to_bottom: [
    { x: 0.5, y: 0.05 },
    { x: 0.5, y: 0.95 },
  ],
};

const blankConfiguration = (): AnimationConfigurationWrite => ({
  name: "",
  description: "",
  asset_id: "",
  impact_asset_id: null,
  animation_type: "projectile",
  trajectory: "origin_to_target",
  movement: "linear",
  origin: { x: 0.95, y: 0.5 },
  target: { x: 0.5, y: 0.5 },
  scale: 1,
  rotation: 0,
  gif_playback_rate: 1,
  travel_duration_ms: 700,
  travel_speed: 0.75,
  impact_time_ms: 0,
  render_layer: 10,
  direction: "auto",
  extra: {},
  associations: [],
});

function interpolate(progress: number, movement: AnimationConfigurationWrite["movement"]): number {
  if (movement === "ease_in") return progress * progress;
  if (movement === "ease_out") return 1 - (1 - progress) ** 2;
  if (movement === "arc") return progress;
  return progress;
}

function useObjectUrl(blob: Blob | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!blob) {
      setUrl(null);
      return;
    }
    const objectUrl = URL.createObjectURL(blob);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [blob]);
  return url;
}

export type AnimationPreviewArenaProps = {
  configuration: AnimationConfigurationWrite;
  asset: AssetRecord | undefined;
  assetFile: Blob | undefined;
  impactFile: Blob | undefined;
  playbackKey?: string | number | null;
  onComplete?: () => void;
};

export function AnimationPreviewArena({
  configuration,
  asset,
  assetFile,
  impactFile,
  playbackKey = null,
  onComplete,
}: AnimationPreviewArenaProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const previousFrameRef = useRef<ParsedFrame | null>(null);
  const playbackTimerRef = useRef<number | null>(null);
  const [frames, setFrames] = useState<ParsedFrame[]>([]);
  const [gifDimensions, setGifDimensions] = useState({ width: 0, height: 0 });
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [decodeError, setDecodeError] = useState<string | null>(null);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [scenario, setScenario] = useState<"neutral" | "night" | "dawn">("neutral");
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;
  const impactUrl = useObjectUrl(impactFile);
  const blobUrl = useObjectUrl(assetFile);
  const configuredDuration = Math.max(0, configuration.travel_duration_ms);
  const duration = configuredDuration;
  const animationProgress =
    reducedMotion || duration === 0 ? (playing ? 1 : 0) : Math.min(1, elapsed / duration);
  const isInstantImpact =
    configuration.animation_type === "impact" ||
    configuration.animation_type === "area" ||
    configuration.trajectory === "direct_impact" ||
    configuration.trajectory === "area_effect";
  const motionProgress = isInstantImpact ? (playing ? 1 : 0) : animationProgress;
  const easedProgress = Math.min(
    1,
    interpolate(motionProgress, configuration.movement) ** (1 / configuration.travel_speed),
  );
  const x =
    configuration.origin.x + (configuration.target.x - configuration.origin.x) * easedProgress;
  const arc = configuration.movement === "arc" ? Math.sin(Math.PI * easedProgress) * 0.18 : 0;
  const y =
    configuration.origin.y +
    (configuration.target.y - configuration.origin.y) * easedProgress -
    arc;
  const impactVisible = playing && (isInstantImpact || animationProgress >= 1);
  const executionDuration = Math.max(
    duration + configuration.impact_time_ms,
    reducedMotion ? 500 : 250,
  );

  useEffect(() => {
    const preference = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!preference) return;
    const updatePreference = () => setReducedMotion(preference.matches);
    updatePreference();
    preference.addEventListener("change", updatePreference);
    return () => preference.removeEventListener("change", updatePreference);
  }, []);
  useEffect(() => {
    let active = true;
    setFrames([]);
    setDecodeError(null);
    setFrameIndex(0);
    setPlaying(false);
    setElapsed(0);
    setStartedAt(null);
    previousFrameRef.current = null;
    if (!assetFile) return;
    Promise.resolve()
      .then(() => assetFile.arrayBuffer())
      .then((buffer) => {
        const parsed = parseGIF(buffer);
        const imageFrames = parsed.frames.filter(
          (frame): frame is Extract<(typeof parsed.frames)[number], { image: unknown }> =>
            "image" in frame,
        );
        const totalFramePixels = imageFrames.reduce(
          (total, frame) => total + frame.image.descriptor.width * frame.image.descriptor.height,
          0,
        );
        if (
          parsed.lsd.width * parsed.lsd.height > 16_000_000 ||
          imageFrames.length > 500 ||
          totalFramePixels > 32_000_000
        ) {
          throw new Error("Este GIF excede os limites de processamento da pré-visualização.");
        }
        const decoded = decompressFrames(parsed, true);
        if (!decoded.length) throw new Error("O GIF não contém frames decodificáveis.");
        if (active) {
          setFrames(decoded);
          setGifDimensions({ width: parsed.lsd.width, height: parsed.lsd.height });
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setDecodeError(error instanceof Error ? error.message : "Não foi possível ler o GIF.");
        }
      });
    return () => {
      active = false;
    };
  }, [assetFile]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const frame = frames[frameIndex];
    if (!canvas || !frame || !gifDimensions.width || !gifDimensions.height) return;
    if (canvas.width !== gifDimensions.width || canvas.height !== gifDimensions.height) {
      canvas.width = gifDimensions.width;
      canvas.height = gifDimensions.height;
      previousFrameRef.current = null;
    }
    const context = canvas.getContext("2d");
    if (!context) return;
    if (frameIndex === 0) {
      context.clearRect(0, 0, canvas.width, canvas.height);
    } else if (previousFrameRef.current?.disposalType === 2) {
      const previous = previousFrameRef.current;
      context.clearRect(
        previous.dims.left,
        previous.dims.top,
        previous.dims.width,
        previous.dims.height,
      );
    }
    const patchCanvas = document.createElement("canvas");
    patchCanvas.width = frame.dims.width;
    patchCanvas.height = frame.dims.height;
    const patchContext = patchCanvas.getContext("2d");
    if (!patchContext) return;
    const patchData = patchContext.createImageData(frame.dims.width, frame.dims.height);
    patchData.data.set(frame.patch);
    patchContext.putImageData(patchData, 0, 0);
    context.drawImage(patchCanvas, frame.dims.left, frame.dims.top);
    previousFrameRef.current = frame;
    if (playing && !reducedMotion && frames.length > 1) {
      const delay = Math.max(20, frame.delay || 100) / configuration.gif_playback_rate;
      playbackTimerRef.current = window.setTimeout(
        () => setFrameIndex((current) => (current + 1) % frames.length),
        delay,
      );
    }
    return () => {
      if (playbackTimerRef.current !== null) {
        window.clearTimeout(playbackTimerRef.current);
        playbackTimerRef.current = null;
      }
    };
  }, [configuration.gif_playback_rate, frameIndex, frames, gifDimensions, playing, reducedMotion]);

  useEffect(() => {
    if (playbackKey === null) return;
    setFrameIndex(0);
    setElapsed(0);
    setStartedAt(performance.now());
    setPlaying(true);
  }, [playbackKey]);

  useEffect(() => {
    if (!playing) return;
    if (startedAt === null) setStartedAt(performance.now());
    let frameRequest = 0;
    const update = (now: number) => {
      const start = startedAt ?? now;
      const nextElapsed = now - start;
      setElapsed(nextElapsed);
      if (nextElapsed >= executionDuration) {
        setPlaying(false);
        setStartedAt(null);
        setFrameIndex(0);
        onCompleteRef.current?.();
        return;
      }
      frameRequest = requestAnimationFrame(update);
    };
    frameRequest = requestAnimationFrame(update);
    return () => cancelAnimationFrame(frameRequest);
  }, [playing, startedAt, executionDuration, reducedMotion]);

  useEffect(
    () => () => {
      if (playbackTimerRef.current !== null) window.clearTimeout(playbackTimerRef.current);
    },
    [],
  );

  function stop(notifyCompletion = false) {
    setPlaying(false);
    setStartedAt(null);
    setElapsed(0);
    setFrameIndex(0);
    if (notifyCompletion) onCompleteRef.current?.();
  }

  return (
    <div>
      <div
        className="relative aspect-video overflow-hidden rounded-lg border border-border bg-[radial-gradient(ellipse_at_center,_hsl(var(--muted))_0%,_hsl(var(--background))_72%)]"
        aria-label="Arena de pré-visualização"
        style={{
          background:
            scenario === "night"
              ? "radial-gradient(ellipse at center, #263044 0%, #111827 80%)"
              : scenario === "dawn"
                ? "radial-gradient(ellipse at center, #f3e8d0 0%, #d7c6a5 80%)"
                : undefined,
        }}
      >
        <div className="absolute inset-y-0 left-1/2 border-l border-dashed border-border/70" />
        <div className="absolute inset-x-0 top-1/2 border-t border-dashed border-border/70" />
        <div
          className="absolute h-8 w-8 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-primary/70 bg-primary/15"
          style={{
            left: `${configuration.target.x * 100}%`,
            top: `${configuration.target.y * 100}%`,
          }}
          aria-label="Alvo fictício"
        />
        <ArrowRight
          className="absolute h-5 w-5 text-primary"
          style={{
            left: `${((configuration.origin.x + configuration.target.x) / 2) * 100}%`,
            top: `${((configuration.origin.y + configuration.target.y) / 2) * 100}%`,
            transform: `translate(-50%, -50%) rotate(${
              Math.atan2(
                configuration.target.y - configuration.origin.y,
                configuration.target.x - configuration.origin.x,
              ) *
              (180 / Math.PI)
            }deg)`,
          }}
          aria-label="Direção do movimento"
        />
        <span
          className="absolute -translate-x-1/2 -translate-y-1/2 text-xs text-muted-foreground"
          style={{
            left: `${configuration.origin.x * 100}%`,
            top: `${configuration.origin.y * 100}%`,
          }}
        >
          Origem
        </span>
        <span
          className="absolute -translate-x-1/2 -translate-y-1/2 text-xs text-muted-foreground"
          style={{
            left: `${configuration.target.x * 100}%`,
            top: `calc(${configuration.target.y * 100}% + 28px)`,
          }}
        >
          Alvo
        </span>
        {blobUrl && frames.length > 0 && (
          <canvas
            ref={canvasRef}
            className="absolute -translate-x-1/2 -translate-y-1/2 object-contain"
            style={{
              left: `${(playing ? x : configuration.origin.x) * 100}%`,
              top: `${(playing ? y : configuration.origin.y) * 100}%`,
              width: `${Math.min(192, 96 * configuration.scale)}px`,
              height: "auto",
              transform: `translate(-50%, -50%) rotate(${
                configuration.rotation +
                (configuration.direction === "up"
                  ? -90
                  : configuration.direction === "down"
                    ? 90
                    : 0)
              }deg) scaleX(${
                configuration.direction === "left" ||
                (configuration.direction === "auto" &&
                  configuration.target.x < configuration.origin.x)
                  ? -1
                  : 1
              })`,
              zIndex: configuration.render_layer,
            }}
            aria-label={asset?.name ?? "Prévia do GIF"}
          />
        )}
        {impactVisible && impactUrl && !reducedMotion && (
          <img
            src={impactUrl}
            alt="Prévia do impacto"
            className="pointer-events-none absolute h-20 w-20 -translate-x-1/2 -translate-y-1/2 object-contain"
            style={{
              left: `${configuration.target.x * 100}%`,
              top: `${configuration.target.y * 100}%`,
            }}
          />
        )}
        {impactVisible && reducedMotion && (
          <div
            className="pointer-events-none absolute h-8 w-8 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-accent bg-accent/30"
            style={{
              left: `${configuration.target.x * 100}%`,
              top: `${configuration.target.y * 100}%`,
            }}
            aria-label="Indicador de impacto reduzido"
          />
        )}
        {reducedMotion && (
          <span className="absolute bottom-2 left-2 rounded bg-background/80 px-2 py-1 text-xs text-muted-foreground">
            Prévia reduzida por preferência de movimento
          </span>
        )}
      </div>
      {decodeError && <p className="mt-2 text-sm text-destructive">{decodeError}</p>}
      {!assetFile && (
        <p className="mt-2 text-sm text-muted-foreground">Selecione um GIF disponível.</p>
      )}
      <label className="mb-2 flex items-center gap-2 text-sm">
        Cenário
        <select
          aria-label="Cenário da arena"
          className="h-9 rounded-md border border-input bg-background px-2"
          value={scenario}
          onChange={(event) => {
            if (
              event.target.value === "neutral" ||
              event.target.value === "night" ||
              event.target.value === "dawn"
            ) {
              setScenario(event.target.value);
            }
          }}
        >
          <option value="neutral">Neutro</option>
          <option value="night">Noite</option>
          <option value="dawn">Amanhecer</option>
        </select>
      </label>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          type="button"
          onClick={() => {
            stop();
            setPlaying(true);
            setStartedAt(performance.now());
          }}
        >
          <Play className="mr-2 h-4 w-4" /> Reproduzir / repetir
        </Button>
        <Button type="button" variant="outline" onClick={() => stop(true)} disabled={!playing}>
          <Square className="mr-2 h-4 w-4" /> Interromper
        </Button>
        <span className="self-center text-xs text-muted-foreground">
          Cenário neutro • {Math.round(x * 100)}%, {Math.round(y * 100)}%
        </span>
      </div>
    </div>
  );
}

export function AnimationEditorPage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<AnimationConfigurationWrite>(blankConfiguration);
  const configurationsQuery = useQuery({
    queryKey: ["admin-animation-configurations"],
    queryFn: listAnimationConfigurations,
  });
  const assetsQuery = useQuery({
    queryKey: ["admin-animation-assets"],
    queryFn: () => listAssets("", ""),
  });
  const associationOptionsQuery = useQuery({
    queryKey: ["admin-animation-association-options"],
    queryFn: listAssetAssociationOptions,
  });
  const configurations = configurationsQuery.data ?? [];
  const gifs = (assetsQuery.data ?? []).filter(
    (asset) => asset.content_type === "image/gif" && asset.extension.toLowerCase() === ".gif",
  );
  const mainFileQuery = useQuery({
    queryKey: ["admin-animation-file", draft.asset_id],
    queryFn: () => getAdminAssetFile(draft.asset_id),
    enabled: Boolean(draft.asset_id),
    retry: false,
  });
  const impactFileQuery = useQuery({
    queryKey: ["admin-animation-file", draft.impact_asset_id],
    queryFn: () => getAdminAssetFile(draft.impact_asset_id!),
    enabled: Boolean(draft.impact_asset_id),
    retry: false,
  });
  const selectedAsset = gifs.find((asset) => asset.id === draft.asset_id);
  const validDraft =
    draft.description.length <= 20000 &&
    draft.scale >= 0.1 &&
    draft.scale <= 5 &&
    draft.rotation >= -3600 &&
    draft.rotation <= 3600 &&
    draft.gif_playback_rate >= 0.1 &&
    draft.gif_playback_rate <= 4 &&
    Number.isInteger(draft.travel_duration_ms) &&
    draft.travel_duration_ms >= 0 &&
    draft.travel_duration_ms <= 30000 &&
    draft.travel_speed > 0 &&
    draft.travel_speed <= 10 &&
    Number.isInteger(draft.impact_time_ms) &&
    draft.impact_time_ms >= 0 &&
    draft.impact_time_ms <= 30000 &&
    Number.isInteger(draft.render_layer) &&
    draft.render_layer >= 0 &&
    draft.render_layer <= 100 &&
    [draft.origin.x, draft.origin.y, draft.target.x, draft.target.y].every(
      (coordinate) => Number.isFinite(coordinate) && coordinate >= 0 && coordinate <= 1,
    );
  const saveMutation = useMutation({
    mutationFn: () => saveAnimationConfiguration(draft, selectedId ?? undefined),
    onSuccess: async (saved) => {
      await queryClient.invalidateQueries({ queryKey: ["admin-animation-configurations"] });
      setSelectedId(saved.id);
      setDraft(toDraft(saved));
      toast.success("Configuração de animação salva.");
    },
    onError: (error) =>
      toast.error("Não foi possível salvar a configuração.", {
        description: error instanceof Error ? error.message : String(error),
      }),
  });
  const deleteMutation = useMutation({
    mutationFn: deleteAnimationConfiguration,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-animation-configurations"] });
      setSelectedId(null);
      setDraft(blankConfiguration());
      toast.success("Configuração excluída.");
    },
    onError: (error) =>
      toast.error("Não foi possível excluir a configuração.", {
        description: error instanceof Error ? error.message : String(error),
      }),
  });

  function toDraft(configuration: AnimationConfigurationRecord): AnimationConfigurationWrite {
    const {
      id: _id,
      is_in_use: _isInUse,
      created_at: _created,
      updated_at: _updated,
      ...values
    } = configuration;
    return {
      ...values,
      associations: configuration.associations.map(({ entity_type, entity_id }) => ({
        entity_type,
        entity_id,
      })),
    };
  }

  function update<K extends keyof AnimationConfigurationWrite>(
    key: K,
    value: AnimationConfigurationWrite[K],
  ) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function selectConfiguration(configuration: AnimationConfigurationRecord) {
    setSelectedId(configuration.id);
    setDraft(toDraft(configuration));
  }

  function toggleAssociation(option: AssetAssociationOption, checked: boolean) {
    const exists = draft.associations.some(
      (association) =>
        association.entity_type === option.entity_type &&
        association.entity_id === option.entity_id,
    );
    if (checked && !exists) {
      update("associations", [
        ...draft.associations,
        { entity_type: option.entity_type, entity_id: option.entity_id },
      ]);
    } else if (!checked) {
      update(
        "associations",
        draft.associations.filter(
          (association) =>
            association.entity_type !== option.entity_type ||
            association.entity_id !== option.entity_id,
        ),
      );
    }
  }

  return (
    <div>
      <PageHeader
        title="Editor de Animações"
        description="Configure e teste animações visuais reutilizáveis sem alterar o estado das campanhas."
        icon={Clapperboard}
        actions={
          <Button
            onClick={() => {
              setSelectedId(null);
              setDraft(blankConfiguration());
            }}
          >
            <Plus className="mr-2 h-4 w-4" /> Nova configuração
          </Button>
        }
      />
      <div className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="text-lg">Configurações salvas</CardTitle>
            <CardDescription>Persistidas no backend e disponíveis após recarregar.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {configurationsQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Carregando configurações…</p>
            ) : configurationsQuery.isError ? (
              <p className="text-sm text-destructive">
                {configurationsQuery.error instanceof Error
                  ? configurationsQuery.error.message
                  : "Falha ao carregar configurações."}
              </p>
            ) : configurations.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nenhuma configuração cadastrada.</p>
            ) : (
              configurations.map((configuration) => (
                <button
                  key={configuration.id}
                  type="button"
                  onClick={() => selectConfiguration(configuration)}
                  className={`w-full rounded-md border p-3 text-left text-sm transition-colors ${
                    selectedId === configuration.id
                      ? "border-primary bg-primary/5"
                      : "border-border hover:bg-muted"
                  }`}
                >
                  <span className="block font-medium">{configuration.name}</span>
                  <span className="text-muted-foreground">
                    {trajectories.find((item) => item.value === configuration.trajectory)?.label}
                  </span>
                </button>
              ))
            )}
          </CardContent>
        </Card>

        <div className="grid min-w-0 gap-5 2xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Configuração</CardTitle>
              <CardDescription>
                Valores de reprodução, deslocamento e impacto são independentes.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <label className="block space-y-1 text-sm">
                Nome
                <Input
                  value={draft.name}
                  maxLength={160}
                  onChange={(event) => update("name", event.target.value)}
                />
              </label>
              <label className="block space-y-1 text-sm">
                Descrição
                <Textarea
                  value={draft.description}
                  maxLength={20000}
                  onChange={(event) => update("description", event.target.value)}
                />
              </label>
              <label className="block space-y-1 text-sm">
                GIF principal
                <select
                  aria-label="GIF principal"
                  className="h-10 w-full rounded-md border border-input bg-background px-3"
                  value={draft.asset_id}
                  onChange={(event) => update("asset_id", event.target.value)}
                >
                  <option value="">Selecione um GIF cadastrado</option>
                  {gifs.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.name}
                    </option>
                  ))}
                </select>
                {assetsQuery.isError && (
                  <span className="text-destructive">Falha ao carregar assets GIF.</span>
                )}
                {mainFileQuery.isError && (
                  <span className="text-destructive">O GIF selecionado não está disponível.</span>
                )}
              </label>
              <label className="block space-y-1 text-sm">
                GIF de impacto (opcional)
                <select
                  aria-label="GIF de impacto"
                  className="h-10 w-full rounded-md border border-input bg-background px-3"
                  value={draft.impact_asset_id ?? ""}
                  onChange={(event) => update("impact_asset_id", event.target.value || null)}
                >
                  <option value="">Sem GIF de impacto</option>
                  {gifs.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.name}
                    </option>
                  ))}
                </select>
                {impactFileQuery.isError && (
                  <span className="text-destructive">O GIF de impacto não está disponível.</span>
                )}
              </label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="space-y-1 text-sm">
                  Tipo
                  <select
                    className="h-10 w-full rounded-md border border-input bg-background px-3"
                    value={draft.animation_type}
                    onChange={(event) =>
                      update(
                        "animation_type",
                        event.target.value as AnimationConfigurationWrite["animation_type"],
                      )
                    }
                  >
                    <option value="projectile">Projétil</option>
                    <option value="impact">Impacto</option>
                    <option value="area">Área</option>
                  </select>
                </label>
                <label className="space-y-1 text-sm">
                  Trajetória
                  <select
                    className="h-10 w-full rounded-md border border-input bg-background px-3"
                    value={draft.trajectory}
                    onChange={(event) => {
                      const trajectory = event.target.value as AnimationTrajectory;
                      update("trajectory", trajectory);
                      const points = trajectoryPoints[trajectory];
                      if (points)
                        setDraft((current) => ({
                          ...current,
                          trajectory,
                          origin: points[0],
                          target: points[1],
                        }));
                    }}
                  >
                    {trajectories.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="space-y-1 text-sm">
                  Movimento
                  <select
                    className="h-10 w-full rounded-md border border-input bg-background px-3"
                    value={draft.movement}
                    onChange={(event) =>
                      update(
                        "movement",
                        event.target.value as AnimationConfigurationWrite["movement"],
                      )
                    }
                  >
                    <option value="linear">Linear</option>
                    <option value="ease_in">Acelera</option>
                    <option value="ease_out">Desacelera</option>
                    <option value="arc">Arco</option>
                  </select>
                </label>
                <label className="space-y-1 text-sm">
                  Escala (0,1–5)
                  <Input
                    type="number"
                    min="0.1"
                    max="5"
                    step="0.1"
                    value={draft.scale}
                    onChange={(event) => update("scale", Number(event.target.value))}
                  />
                </label>
                <label className="space-y-1 text-sm">
                  Rotação (graus)
                  <Input
                    type="number"
                    min="-3600"
                    max="3600"
                    value={draft.rotation}
                    onChange={(event) => update("rotation", Number(event.target.value))}
                  />
                </label>
                <label className="space-y-1 text-sm">
                  Velocidade de reprodução do GIF (×)
                  <Input
                    type="number"
                    min="0.1"
                    max="4"
                    step="0.1"
                    value={draft.gif_playback_rate}
                    onChange={(event) => update("gif_playback_rate", Number(event.target.value))}
                  />
                </label>
                <label className="space-y-1 text-sm">
                  Duração do deslocamento (ms)
                  <Input
                    type="number"
                    min="0"
                    max="30000"
                    step="10"
                    value={draft.travel_duration_ms}
                    onChange={(event) => update("travel_duration_ms", Number(event.target.value))}
                  />
                  <span className="block text-xs text-muted-foreground">
                    0 representa deslocamento instantâneo.
                  </span>
                </label>
                <label className="space-y-1 text-sm">
                  Velocidade de deslocamento (×)
                  <Input
                    type="number"
                    min="0.01"
                    max="10"
                    step="0.05"
                    value={draft.travel_speed}
                    onChange={(event) => update("travel_speed", Number(event.target.value))}
                  />
                </label>
                <label className="space-y-1 text-sm">
                  Tempo de impacto (ms)
                  <Input
                    type="number"
                    min="0"
                    max="30000"
                    step="10"
                    value={draft.impact_time_ms}
                    onChange={(event) => update("impact_time_ms", Number(event.target.value))}
                  />
                </label>
                <label className="space-y-1 text-sm">
                  Camada de renderização (0–100)
                  <Input
                    type="number"
                    min="0"
                    max="100"
                    value={draft.render_layer}
                    onChange={(event) => update("render_layer", Number(event.target.value))}
                  />
                </label>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {(["origin", "target"] as const).map((field) => (
                  <label key={field} className="space-y-1 text-sm">
                    {field === "origin" ? "Origem x, y (0–1)" : "Destino x, y (0–1)"}
                    <div className="grid grid-cols-2 gap-2">
                      <Input
                        aria-label={`${field} x`}
                        type="number"
                        min="0"
                        max="1"
                        step="0.01"
                        value={draft[field].x}
                        onChange={(event) => {
                          const next = Number(event.target.value);
                          if (Number.isFinite(next) && next >= 0 && next <= 1) {
                            update(field, { ...draft[field], x: next });
                          }
                        }}
                      />
                      <Input
                        aria-label={`${field} y`}
                        type="number"
                        min="0"
                        max="1"
                        step="0.01"
                        value={draft[field].y}
                        onChange={(event) => {
                          const next = Number(event.target.value);
                          if (Number.isFinite(next) && next >= 0 && next <= 1) {
                            update(field, { ...draft[field], y: next });
                          }
                        }}
                      />
                    </div>
                  </label>
                ))}
              </div>
              <label className="block space-y-1 text-sm">
                Direção
                <select
                  className="h-10 w-full rounded-md border border-input bg-background px-3"
                  value={draft.direction}
                  onChange={(event) =>
                    update(
                      "direction",
                      event.target.value as AnimationConfigurationWrite["direction"],
                    )
                  }
                >
                  <option value="auto">Automática</option>
                  <option value="left">Esquerda</option>
                  <option value="right">Direita</option>
                  <option value="up">Cima</option>
                  <option value="down">Baixo</option>
                </select>
              </label>
              <fieldset className="space-y-2 rounded-md border p-3">
                <legend className="px-1 text-sm font-medium">Associações com entidades</legend>
                {associationOptionsQuery.isLoading ? (
                  <p className="text-sm text-muted-foreground">Carregando entidades…</p>
                ) : associationOptionsQuery.isError ? (
                  <p className="text-sm text-destructive">
                    Não foi possível carregar as entidades.
                  </p>
                ) : (
                  <div className="max-h-36 space-y-1 overflow-y-auto">
                    {(associationOptionsQuery.data ?? []).map((option) => {
                      const checked = draft.associations.some(
                        (entry) =>
                          entry.entity_type === option.entity_type &&
                          entry.entity_id === option.entity_id,
                      );
                      return (
                        <label
                          key={`${option.entity_type}:${option.entity_id}`}
                          className="flex items-center gap-2 text-sm"
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(event) => toggleAssociation(option, event.target.checked)}
                          />
                          {option.entity_name}{" "}
                          <span className="text-muted-foreground">({option.entity_type})</span>
                        </label>
                      );
                    })}
                  </div>
                )}
              </fieldset>
              <div className="flex flex-wrap gap-2">
                <Button
                  onClick={() => saveMutation.mutate()}
                  disabled={
                    saveMutation.isPending ||
                    !draft.name.trim() ||
                    !draft.asset_id ||
                    !validDraft ||
                    mainFileQuery.isError ||
                    impactFileQuery.isError
                  }
                >
                  <Save className="mr-2 h-4 w-4" />{" "}
                  {saveMutation.isPending ? "Salvando…" : "Salvar configuração"}
                </Button>
                {selectedId && (
                  <>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setSelectedId(null);
                        setDraft({ ...draft, name: `${draft.name} (cópia)` });
                      }}
                    >
                      <Copy className="mr-2 h-4 w-4" /> Duplicar
                    </Button>
                    <ConfirmDialog
                      trigger={
                        <Button type="button" variant="destructive">
                          <Trash2 className="mr-2 h-4 w-4" /> Excluir
                        </Button>
                      }
                      title="Excluir configuração?"
                      description="A configuração será removida. Registros associados precisam ser desassociados antes."
                      onConfirm={() => deleteMutation.mutate(selectedId)}
                    />
                  </>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Arena de pré-visualização</CardTitle>
              <CardDescription>
                O teste é local à prévia e não aplica dano nem altera campanhas.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {assetsQuery.isLoading ? (
                <p className="text-sm text-muted-foreground">Carregando GIF…</p>
              ) : assetsQuery.isError ? (
                <p className="text-sm text-destructive">
                  Não foi possível carregar os GIFs disponíveis.
                </p>
              ) : !selectedAsset ? (
                <EmptyState
                  title="Selecione um GIF"
                  text="Escolha um GIF cadastrado na Biblioteca de Assets."
                />
              ) : mainFileQuery.isLoading ? (
                <p className="text-sm text-muted-foreground">Carregando prévia protegida…</p>
              ) : mainFileQuery.isError ? (
                <p className="text-sm text-destructive">
                  O asset não está disponível para pré-visualização.
                </p>
              ) : (
                <AnimationPreviewArena
                  configuration={draft}
                  asset={selectedAsset}
                  assetFile={mainFileQuery.data}
                  impactFile={impactFileQuery.data}
                />
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
