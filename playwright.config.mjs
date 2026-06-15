import { defineConfig } from '@playwright/test';

const baseURL = process.env.XV7_BROWSER_BASE_URL || 'http://localhost:3000';

export default defineConfig({
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
});
