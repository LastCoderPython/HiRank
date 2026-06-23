import { test, expect } from '@playwright/test';

test.describe('Chat Streaming interface', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/auth/session', async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify({ authenticated: false, user: null }) });
    });
    await page.route('**/api/v1/temp-chats/*', async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify({ exists: false, messages: [] }) });
    });
    await page.route('**/api/v1/chats', async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify({ chat_id: 'mock-chat-id' }) });
    });
    await page.addInitScript(() => {
      window.sessionStorage.setItem('guest_mode', 'true');
    });
  });

  test('should allow anonymous user to send a prompt and get a response', async ({ page }) => {
    // We must mock the API response for /api/v1/chat to avoid hitting the actual backend
    // which requires ChromaDB and OpenAI credits during E2E testing.
    
    // Create an artificial stream response
    await page.route('**/api/v1/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'data: {"type": "session", "session_id": "test-session"}\n\ndata: {"type": "token", "data": "Hello"}\n\ndata: {"type": "token", "data": " world!"}\n\ndata: {"type": "done", "tavily_skipped": true}\n\n'
      });
    });

    await page.goto('/');

    // Type a message
    const textarea = page.locator('textarea[placeholder="Message Aariv AI"]');
    await textarea.fill('What is AEC?');
    
    // Press enter or click send
    await page.keyboard.press('Enter');

    // Verify the message appears in chat
    await expect(page.locator('text=What is AEC?')).toBeVisible();

    // Verify the streamed response appears
    await expect(page.locator('text=Hello world!')).toBeVisible();
  });

  test('should show auth wall on limit exceeded', async ({ page }) => {
    await page.route('**/api/v1/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'data: {"type": "auth_required", "reason": "prompt_limit"}\n\n'
      });
    });

    await page.goto('/');

    await page.locator('textarea[placeholder="Message Aariv AI"]').fill('What is AEC?');
    await page.keyboard.press('Enter');

    // Verify the toast appears
    await expect(page.getByRole('button', { name: '📱 Sign in' })).toBeVisible();
  });
});
