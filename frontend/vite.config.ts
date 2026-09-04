import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, ".", "");
  if (command === "build" && env.RENDER === "true") {
    const raw = env.VITE_API_BASE_URL || "";
    // The production FastAPI service serves this bundle, so an empty value intentionally
    // keeps all /api requests on the same origin. A separate API origin remains supported.
    if (raw) {
      const url = new URL(raw);
      if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash
          || (url.pathname !== "/" && url.pathname !== "") || ["localhost", "127.0.0.1", "[::1]"].indexOf(url.hostname) >= 0) {
        throw new Error("VITE_API_BASE_URL must be empty for same-origin deployment or a public HTTPS root URL (without /api)");
      }
    }
  }
  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": "http://127.0.0.1:8000",
      },
    },
  };
});

