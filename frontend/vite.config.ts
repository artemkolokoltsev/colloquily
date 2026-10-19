import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve, sep } from "node:path";
import { cpSync, createReadStream, existsSync, statSync } from "node:fs";
const pdfAssets = resolve(__dirname, "../node_modules/pdfjs-dist");
const assetDirectories = ["cmaps", "standard_fonts", "wasm"];

export default defineConfig({
  root: resolve(__dirname),
  plugins: [
    react(),
    {
      name: "offline-pdf-assets",
      configureServer(server) {
        server.middlewares.use("/pdfjs", (req, res, next) => {
          const relative = decodeURIComponent(
            (req.url || "").split("?")[0],
          ).replace(/^\//, "");
          if (!assetDirectories.includes(relative.split("/")[0])) return next();
          const path = resolve(pdfAssets, relative);
          if (
            !path.startsWith(pdfAssets + sep) ||
            !existsSync(path) ||
            !statSync(path).isFile()
          )
            return next();
          res.setHeader(
            "Content-Type",
            path.endsWith(".wasm")
              ? "application/wasm"
              : "application/octet-stream",
          );
          createReadStream(path).pipe(res);
        });
      },
      writeBundle() {
        for (const directory of assetDirectories)
          cpSync(
            resolve(pdfAssets, directory),
            resolve(__dirname, "dist/pdfjs", directory),
            { recursive: true },
          );
      },
    },
  ],
  clearScreen: false,
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
