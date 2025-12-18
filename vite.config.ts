import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    host: "0.0.0.0",
    port: 3005,
    allowedHosts: [
      "employ-tropical-sue-blessed.trycloudflare.com",
      ".trycloudflare.com",
      "localhost",
      "198.41.200.43",
    ],
  },
});
