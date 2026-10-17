import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  root: frontendRoot,
  plugins: [react()],
  // C2 launches Vite locally; never expose the dev-server response to foreign origins.
  // Defense in depth for esbuild's older CORS advisory until a reviewed Vite upgrade.
  server: {
    host: "127.0.0.1",
    strictPort: true,
    cors: { origin: /^http:\/\/(?:127\.0\.0\.1|localhost):5173$/ },
  },
  build: {
    outDir: resolve(frontendRoot, "dist"),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        app: resolve(frontendRoot, "index.html"),
      },
    },
  },
});
