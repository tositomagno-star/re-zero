const DEFAULT_API_ORIGIN = "http://127.0.0.1:8000";

export function resolveApiOrigin(
  configuredApiUrl: string | undefined = import.meta.env["VITE_API_URL"],
  currentHostname?: string,
): string {
  const hostname = currentHostname?.toLowerCase();
  const localApiOrigin =
    hostname === "localhost" || hostname === "127.0.0.1"
      ? `http://${hostname}:8000`
      : DEFAULT_API_ORIGIN;
  return (configuredApiUrl ?? localApiOrigin).replace(/\/+$/, "");
}

export const apiOrigin = resolveApiOrigin(
  undefined,
  typeof window === "undefined" ? undefined : window.location.hostname,
);
