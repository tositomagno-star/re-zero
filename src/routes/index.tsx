import { createFileRoute } from "@tanstack/react-router";

import { LandingPage } from "../components/player/PlayerPages";

export const Route = createFileRoute("/")({
  component: LandingPage,
});
