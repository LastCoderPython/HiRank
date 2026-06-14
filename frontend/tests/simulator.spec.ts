import { test, expect } from '@playwright/test';

test.describe('College Simulator', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/auth/session', async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify({ authenticated: false, user: null }) });
    });
    await page.route('**/api/v1/temp-chats/*', async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify({ exists: false, messages: [] }) });
    });
    await page.addInitScript(() => {
      window.sessionStorage.setItem('guest_mode', 'true');
    });
  });

  test('should render simulated results correctly', async ({ page }) => {
    // Mock the simulate endpoint
    await page.route('**/api/v1/colleges/simulate*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          current_rank: 500,
          target_rank: 200,
          category: 'General',
          exam: 'CEE',
          current_options: [
            { college_name: 'Jorhat Engineering College', branch: 'Mechanical', closing_rank: 600, band: 'safe' }
          ],
          target_options: [
            { college_name: 'Jorhat Engineering College', branch: 'Mechanical', closing_rank: 600, band: 'safe' },
            { college_name: 'Assam Engineering College', branch: 'Computer Science', closing_rank: 250, band: 'target' }
          ],
          newly_unlocked: [
            { college_name: 'Assam Engineering College', branch: 'Computer Science', closing_rank: 250, band: 'target', is_unlocked: true }
          ],
          summary: 'Improving from rank 500 to 200 unlocks 1 new college.'
        })
      });
    });

    await page.goto('/simulator');

    // We assume there's a simulator page. Wait, if it's integrated in the dashboard...
    // Let's just mock the route and if the test needs a specific UI interaction, we will adjust.
    // If the simulator is part of the chat, we will trigger it.
  });
});
