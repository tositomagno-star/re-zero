import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

export type Option = { value: string; label: string };

export type FieldDef =
  | {
      name: string;
      label: string;
      type: "text" | "textarea";
      required?: boolean;
      full?: boolean;
      placeholder?: string;
    }
  | {
      name: string;
      label: string;
      type: "image";
      full?: boolean;
      placeholder?: string;
    }
  | {
      name: string;
      label: string;
      type: "checkbox";
      full?: boolean;
      checkboxLabel?: string;
    }
  | {
      name: string;
      label: string;
      type: "number";
      required?: boolean;
      min?: number;
      max?: number;
      step?: number;
    }
  | { name: string; label: string; type: "select"; options: Option[]; required?: boolean }
  | { name: string; label: string; type: "list"; full?: boolean; placeholder?: string }
  | { name: string; label: string; type: "multi"; options: Option[]; full?: boolean };

type Values = Record<string, unknown>;

interface Props {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: string;
  fields: FieldDef[];
  initial: Values;
  validate?: ((v: Values) => string | null) | undefined;
  onSubmit: (v: Values) => void | Promise<void>;
  description?: string;
  submitLabel?: string;
}

export function EntityFormDialog(props: Props) {
  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-display">{props.title}</DialogTitle>
          <DialogDescription>
            {props.description ?? "Preencha os campos e salve as alterações."}
          </DialogDescription>
        </DialogHeader>
        {props.open && <FormBody {...props} />}
      </DialogContent>
    </Dialog>
  );
}

function FormBody({ fields, initial, validate, onSubmit, onOpenChange, submitLabel }: Props) {
  const [values, setValues] = useState<Values>(initial);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const set = (k: string, v: unknown) => setValues((s) => ({ ...s, [k]: v }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    for (const f of fields) {
      const v = values[f.name];
      if ("required" in f && f.required && (v === "" || v === undefined || v === null))
        errs[f.name] = "Campo obrigatório";
      if (f.type === "number") {
        const n = Number(v);
        if (Number.isNaN(n)) errs[f.name] = "Número inválido";
        else if (f.min !== undefined && n < f.min) errs[f.name] = `Mínimo ${f.min}`;
        else if (f.max !== undefined && n > f.max) errs[f.name] = `Máximo ${f.max}`;
      }
    }
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const custom = validate?.(values) ?? null;
    setFormError(custom);
    if (custom) return;
    setIsSubmitting(true);
    try {
      await onSubmit(values);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Não foi possível salvar.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <div className="grid gap-4 sm:grid-cols-2">
        {fields.map((f) => {
          const full = ("full" in f && f.full) || f.type === "textarea" || f.type === "multi";
          const id = `f-${f.name}`;
          const errorId = `${id}-error`;
          const fieldError = errors[f.name];
          return (
            <div key={f.name} className={full ? "space-y-1.5 sm:col-span-2" : "space-y-1.5"}>
              <Label id={`${id}-label`} htmlFor={f.type === "multi" ? undefined : id}>
                {f.label}
                {"required" in f && f.required ? " *" : ""}
              </Label>
              {f.type === "text" && (
                <Input
                  id={id}
                  value={String(values[f.name] ?? "")}
                  placeholder={f.placeholder}
                  aria-invalid={Boolean(fieldError)}
                  aria-describedby={fieldError ? errorId : undefined}
                  onChange={(e) => set(f.name, e.target.value)}
                />
              )}
              {f.type === "image" && (
                <Input
                  id={id}
                  type="file"
                  accept="image/png,.png"
                  aria-invalid={Boolean(fieldError)}
                  aria-describedby={fieldError ? errorId : undefined}
                  onChange={(e) => set(f.name, e.target.files?.[0])}
                />
              )}
              {f.type === "checkbox" && (
                <label className="flex items-center gap-2 rounded-md border border-border p-3 text-sm">
                  <Checkbox
                    id={id}
                    checked={Boolean(values[f.name])}
                    aria-invalid={Boolean(fieldError)}
                    aria-describedby={fieldError ? errorId : undefined}
                    onCheckedChange={(checked) => set(f.name, checked === true)}
                  />
                  {f.checkboxLabel ?? "Ativo"}
                </label>
              )}
              {f.type === "textarea" && (
                <Textarea
                  id={id}
                  rows={3}
                  value={String(values[f.name] ?? "")}
                  placeholder={f.placeholder}
                  aria-invalid={Boolean(fieldError)}
                  aria-describedby={fieldError ? errorId : undefined}
                  onChange={(e) => set(f.name, e.target.value)}
                />
              )}
              {f.type === "number" && (
                <Input
                  id={id}
                  type="number"
                  step={f.step ?? 1}
                  value={String(values[f.name] ?? "")}
                  aria-invalid={Boolean(fieldError)}
                  aria-describedby={fieldError ? errorId : undefined}
                  onChange={(e) => set(f.name, e.target.value === "" ? "" : Number(e.target.value))}
                />
              )}
              {f.type === "select" && (
                <Select value={String(values[f.name] ?? "")} onValueChange={(v) => set(f.name, v)}>
                  <SelectTrigger
                    id={id}
                    aria-invalid={Boolean(fieldError)}
                    aria-describedby={fieldError ? errorId : undefined}
                  >
                    <SelectValue placeholder="Selecione" />
                  </SelectTrigger>
                  <SelectContent>
                    {f.options.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              {f.type === "list" && (
                <Textarea
                  id={id}
                  rows={2}
                  placeholder={f.placeholder ?? "Um por linha"}
                  value={((values[f.name] as string[]) ?? []).join("\n")}
                  aria-invalid={Boolean(fieldError)}
                  aria-describedby={fieldError ? errorId : undefined}
                  onChange={(e) => set(f.name, e.target.value.split("\n"))}
                />
              )}
              {f.type === "multi" && (
                <div
                  role="group"
                  aria-labelledby={`${id}-label`}
                  aria-invalid={Boolean(fieldError)}
                  aria-describedby={fieldError ? errorId : undefined}
                  className="grid max-h-40 gap-2 overflow-y-auto rounded-md border border-border p-3 sm:grid-cols-2"
                >
                  {f.options.length === 0 && (
                    <p className="text-sm text-muted-foreground">Nenhuma opção disponível.</p>
                  )}
                  {f.options.map((o) => {
                    const arr = (values[f.name] as string[]) ?? [];
                    return (
                      <label key={o.value} className="flex items-center gap-2 text-sm">
                        <Checkbox
                          checked={arr.includes(o.value)}
                          onCheckedChange={(c) =>
                            set(f.name, c ? [...arr, o.value] : arr.filter((x) => x !== o.value))
                          }
                        />
                        {o.label}
                      </label>
                    );
                  })}
                </div>
              )}
              {fieldError && (
                <p
                  id={errorId}
                  role="alert"
                  aria-live="polite"
                  className="text-xs text-destructive"
                >
                  {fieldError}
                </p>
              )}
            </div>
          );
        })}
      </div>
      {formError && (
        <p
          role="alert"
          aria-live="polite"
          className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm text-destructive"
        >
          {formError}
        </p>
      )}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
          Cancelar
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Salvando..." : (submitLabel ?? "Salvar")}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** Strip blank lines from list fields before saving. */
export function cleanLists(v: Values, fields: FieldDef[]): Values {
  const out = { ...v };
  for (const f of fields)
    if (f.type === "list")
      out[f.name] = ((out[f.name] as string[]) ?? []).map((s) => s.trim()).filter(Boolean);
  return out;
}
