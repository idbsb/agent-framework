import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, ".", "");
  if (command === "build" && env.VERCEL === "1") {
    const raw = env.VITE_API_BASE_URL || "";
    if (!raw) throw new Error("Vercel builds require VITE_API_BASE_URL");
    const url = new URL(raw); // fail the deployment build instead of silently using the Vercel host
    if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash
        || (url.pathname !== "/" && url.pathname !== "") || ["localhost", "127.0.0.1", "[::1]"].indexOf(url.hostname) >= 0) {
      throw new Error("VITE_API_BASE_URL must be the public Render HTTPS root URL (without /api)");
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

