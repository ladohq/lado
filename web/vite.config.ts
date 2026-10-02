import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The bundle goes into the Python package: the wheel ships it, users need no Node.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/lado/server/static",
    emptyOutDir: true,
  },
  test: {
    environment: "jsdom",
  },
});
