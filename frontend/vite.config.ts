import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    allowedHosts: true,
  },
  build: {
    // three.js alone is over 500 kB minified; the split below keeps it in its own cached file.
    chunkSizeWarningLimit: 1200,
    rolldownOptions: {
      output: {
        // Libraries change far less often than app code, so a redeploy only re-downloads the app chunk.
        codeSplitting: {
          groups: [
            { name: 'three', test: /node_modules[\\/](three|@react-three|postprocessing|three-stdlib|maath|camera-controls|troika-|meshline|stats-gl|detect-gpu|@monogrid|n8ao)/, priority: 2 },
            { name: 'vendor', test: /node_modules/, priority: 1 },
          ],
        },
      },
    },
  },
})
