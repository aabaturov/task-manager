import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During local `npm run dev`, proxy API calls to the FastAPI server so the
// session cookie works on a single origin.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
