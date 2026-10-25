import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "src") },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    // Used by `npm run test:coverage` (CI); lcov is what SonarQube Cloud reads (plan 012).
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      // mock.ts is the dev-only fake backend (NEXT_PUBLIC_API_MOCK=1), not site code.
      exclude: ["src/**/*.test.{ts,tsx}", "src/lib/mock.ts"],
      reporter: ["text-summary", "lcov"],
    },
  },
});
