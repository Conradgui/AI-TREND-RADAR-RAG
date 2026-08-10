import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: { timeout: 8_000 },
  reporter: 'line',
  use: {
    headless: true,
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'static',
      use: { baseURL: 'http://127.0.0.1:4173' },
    },
    {
      name: 'fastapi',
      use: { baseURL: 'http://127.0.0.1:4174' },
    },
  ],
  webServer: [
    {
      command: 'exec python3 -m http.server 4173 --bind 127.0.0.1',
      url: 'http://127.0.0.1:4173/manifest.json',
      reuseExistingServer: false,
    },
    {
      command: 'exec .venv/bin/python -m uvicorn rag.server:app --host 127.0.0.1 --port 4174',
      url: 'http://127.0.0.1:4174/health',
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
})
