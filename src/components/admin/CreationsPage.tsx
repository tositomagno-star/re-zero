import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ItemsPage, MonstersPage, PlayersAndCharactersPage, SkillsPage } from "./ManagementPages";
import { AssetLibraryPage } from "./AssetLibraryPage";
import { AnimationEditorPage } from "./AnimationEditorPage";

const categories = [
  { value: "items", label: "Itens, materiais e consumíveis" },
  { value: "skills", label: "Habilidades" },
  { value: "enemies", label: "Inimigos e bosses" },
  { value: "characters", label: "Personagens e NPCs" },
  { value: "visuals", label: "GIFs e animações" },
] as const;

const descriptions: Record<(typeof categories)[number]["value"], string> = {
  items:
    "Cadastre armas, armaduras, acessórios, consumíveis e materiais. A categoria do item define seu uso; configure também atributos, efeitos e ficha visual de combate.",
  skills:
    "Crie habilidades de dano, cura ou suporte, defina custo, alcance e alvo e configure os GIFs de execução e projétil.",
  enemies:
    "Cadastre inimigos, minibosses e bosses, seus atributos, comportamento de turno, XP, ouro e itens que podem deixar ao serem derrotados.",
  characters:
    "Cadastre personagens e NPCs e configure suas imagens, animações e associações de combate.",
  visuals:
    "Envie os GIFs uma vez para a biblioteca e reutilize-os nas fichas de itens, habilidades, personagens e inimigos.",
};

export function CreationsPage() {
  const [category, setCategory] = useState<(typeof categories)[number]["value"]>("items");

  return (
    <section className="space-y-5">
      <header>
        <p className="mb-2 text-xs font-medium uppercase tracking-[0.2em] text-primary">
          Conteúdo do jogo
        </p>
        <h1 className="font-display text-3xl">Criações</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          Cadastre e configure o conteúdo do mundo por categoria. Os registros continuam nos
          catálogos oficiais do jogo e podem ser reutilizados em combate, missões e recompensas.
        </p>
      </header>

      <Tabs
        value={category}
        onValueChange={(value) => setCategory(value as (typeof categories)[number]["value"])}
      >
        <TabsList className="flex h-auto w-full justify-start gap-1 overflow-x-auto">
          {categories.map((entry) => (
            <TabsTrigger key={entry.value} value={entry.value} className="whitespace-nowrap">
              {entry.label}
            </TabsTrigger>
          ))}
        </TabsList>

        {categories.map((entry) => (
          <TabsContent key={entry.value} value={entry.value} className="space-y-5">
            <Card className="border-primary/20 bg-primary/5">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">{entry.label}</CardTitle>
                <CardDescription>{descriptions[entry.value]}</CardDescription>
              </CardHeader>
              {entry.value === "items" && (
                <CardContent className="pt-0 text-sm text-muted-foreground">
                  Selecione o tipo real do item — arma, armadura, consumível ou material — e marque
                  “Subclasse de carreira” separadamente quando ele fizer parte de uma carreira.
                  Depois de salvar, envie os GIFs diretamente nos campos de execução e projétil.
                </CardContent>
              )}
              {entry.value === "skills" && (
                <CardContent className="pt-0 text-sm text-muted-foreground">
                  A categoria define o tipo da habilidade; “Subclasse de carreira” é uma marcação
                  separada e também pode ser usada em magias.
                </CardContent>
              )}
              {entry.value === "enemies" && (
                <CardContent className="pt-0 text-sm text-muted-foreground">
                  Para o combate usar um inimigo, publique o perfil de combate. Os drops são
                  configurados na seção de recompensas desta categoria.
                </CardContent>
              )}
            </Card>
            {entry.value === "items" && <ItemsPage />}
            {entry.value === "skills" && <SkillsPage />}
            {entry.value === "enemies" && <MonstersPage />}
            {entry.value === "characters" && (
              <PlayersAndCharactersPage key="creation-characters" initialTab="characters" />
            )}
            {entry.value === "visuals" && (
              <Tabs defaultValue="assets">
                <TabsList className="mb-4">
                  <TabsTrigger value="assets">Biblioteca de GIFs</TabsTrigger>
                  <TabsTrigger value="animations">Configuração avançada</TabsTrigger>
                </TabsList>
                <TabsContent value="assets">
                  <AssetLibraryPage />
                </TabsContent>
                <TabsContent value="animations">
                  <AnimationEditorPage />
                </TabsContent>
              </Tabs>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </section>
  );
}
