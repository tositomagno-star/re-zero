import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api-origin", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-origin")>();
  return { ...actual, apiOrigin: "https://shared-api.example.test" };
});

import { apiOrigin, resolveApiOrigin } from "@/lib/api-origin";
import { adminContentRequest } from "@/lib/admin-content-api";
import { loginPlayer } from "@/lib/auth-api";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("API origin", () => {
  it("preserves the current default origin", () => {
    expect(resolveApiOrigin(undefined)).toBe("http://127.0.0.1:8000");
  });

  it("uses the current local host so session cookies stay same-site", () => {
    expect(resolveApiOrigin(undefined, "localhost")).toBe("http://localhost:8000");
    expect(resolveApiOrigin(undefined, "127.0.0.1")).toBe("http://127.0.0.1:8000");
  });

  it("does not rewrite an explicitly configured API URL", () => {
    expect(resolveApiOrigin("https://api.example.test///", "localhost")).toBe(
      "https://api.example.test",
    );
  });

  it("supports a custom URL and removes trailing slashes", () => {
    expect(resolveApiOrigin("https://api.example.test///")).toBe("https://api.example.test");
  });

  it("reads the custom Vite environment variable", () => {
    vi.stubEnv("VITE_API_URL", "https://configured-api.example.test///");

    expect(resolveApiOrigin()).toBe("https://configured-api.example.test");
  });

  it("is shared by the authentication and admin content clients", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "user-1", username: "player", display_name: "Player" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({}), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await loginPlayer("player", "123456");
    await adminContentRequest("/api/admin/content/chapters");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `${apiOrigin}/api/auth/login`,
      expect.objectContaining({ credentials: "include" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `${apiOrigin}/api/admin/content/chapters`,
      expect.objectContaining({ credentials: "include" }),
    );
  });
});
