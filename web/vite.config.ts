import { defineConfig } from "vite";
import solid from "vite-plugin-solid";

export default defineConfig({
  base: "/ui/",
  plugins: [solid()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false
  }
});
