import { defineConfig } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const baseURL = process.env.XV7_BROWSER_BASE_URL || 'http://localhost:3000';
const skipWebServer = process.env.XV7_SKIP_WEBSERVER === 'true';

const config = {
  testDir: './e2e',
  testMatch: '**/*.spec.mjs',
  timeout: 60_000,
  expect: {
    timeout: 15_000,
  },
  reporter: [['line']],
  use: {
    baseURL,
    trace: 'retain-on-failure',
  },
};

if (!skipWebServer) {
  config.webServer = {
    command: 'npx http-server public -p 3000 -c-1 --gzip false',
    port: 3000,
    url: 'http://localhost:3000',
    reuseExistingServer: true,
    timeout: 30_000,
  };
}

export default defineConfig(config);
