import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const proxy = {
  '/api': process.env.POWERPILOT_API ?? 'http://localhost:8000',
}

export default defineConfig({
  plugins: [vue()],
  build: {
    chunkSizeWarningLimit: 1600,
  },
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
})
