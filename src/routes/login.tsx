import { createFileRoute } from "@tanstack/react-router";

import { AccessPlaceholder } from "../components/player/PlayerPages";

export const Route = createFileRoute("/login")({
  component: () => <AccessPlaceholder mode="login" />,
});
