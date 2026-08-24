import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: { timeout: 8_000 },
  reporter: 'line',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    headless: true,
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'exec python3 -m http.server 4173 --bind 127.0.0.1',
    url: 'http://127.0.0.1:4173/manifest.json',
    reuseExistingServer: false,
  },
})
