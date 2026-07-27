import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Lido via globalThis para nao exigir @types/node so por causa desta linha.
const nodeEnv = (globalThis as { process?: { env?: Record<string, string | undefined> } })
  .process?.env;
const envPort = Number(nodeEnv?.PORT);

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: Number.isFinite(envPort) && envPort > 0 ? envPort : 5173,
    strictPort: false,
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
    strictPort: false,
  },
});
