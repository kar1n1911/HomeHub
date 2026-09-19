import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api/households": "http://localhost:8001",
      "/api/tasks": "http://localhost:8002",
      "/api/devices": "http://localhost:8003"
    }
  }
});

