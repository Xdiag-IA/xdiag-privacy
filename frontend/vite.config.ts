import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const envPort = Number(process.env.PORT);

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
