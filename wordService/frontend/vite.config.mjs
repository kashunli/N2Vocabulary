import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/",
  build: {
    outDir: "../static/react-rail",
    emptyOutDir: true,
  },
  server: {
    host: "127.0.0.1",
    port: 4174,
    proxy: {
      "/api": "http://127.0.0.1:8767",
      "/audio": "http://127.0.0.1:8767",
    },
  },
});
