import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  build: {
    outDir: "../assets/workspace",
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      input: { workspace: "src/main.jsx" },
      output: {
        entryFileNames: "workspace.js",
        assetFileNames: info => info.names.some(name => name.endsWith(".css")) ? "workspace.css" : "[name]-[hash][extname]",
      },
    },
  },
});
