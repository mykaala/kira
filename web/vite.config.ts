import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // KIRA_API points the dev server at another backend (e.g. a second checkout on another port)
  server: { proxy: { "/api": process.env.KIRA_API ?? "http://localhost:8000" } },
});
