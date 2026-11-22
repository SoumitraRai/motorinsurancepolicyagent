// Local preview (npm run preview:local): serves preview.html, which reads ../samples/output.
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: { open: "/preview.html", fs: { allow: [".."] } },
});
