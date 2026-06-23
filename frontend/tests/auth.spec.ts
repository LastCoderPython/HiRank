import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Mock backend session and temp chat to prevent hanging
    await page.route('**/api/v1/auth/session', async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify({ authenticated: false, user: null }) });
    });
    await page.route('**/api/v1/temp-chats/*', async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify({ exists: false, messages: [] }) });
    });
  });

  test('should show guest mode options correctly', async ({ page }) => {
    // Navigate and set guest mode manually
    await page.goto('/');
    await page.evaluate(() => window.sessionStorage.setItem('guest_mode', 'true'));
    await page.reload();

    // Wait for the app to load
    await page.waitForSelector('textarea[placeholder="Message Aariv AI"]');

    // Click settings to see auth options
    await page.click('button[title="Settings"]');

    // Should see guest account info
    await expect(page.locator('text=Guest Account')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Create Free Account' })).toBeVisible();
  });

  test('should open auth landing page', async ({ page }) => {
    // Navigate and set guest mode manually
    await page.goto('/');
    await page.evaluate(() => window.sessionStorage.setItem('guest_mode', 'true'));
    await page.reload();

    await page.click('button[title="Settings"]');
    await page.click('text=Create Free Account');

    // Wait for the reload to land on the Auth page
    await page.waitForLoadState('networkidle');

    // Should see the landing auth form
    await expect(page.getByPlaceholder('you@example.com')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Continue with Email' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeVisible();
  });
});
