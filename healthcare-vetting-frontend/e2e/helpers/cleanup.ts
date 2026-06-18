/**
 * Shared cleanup helper — purges all @test.viperai accounts after test runs.
 * Requires admin credentials to call the purge endpoint.
 */
import type { APIRequestContext } from "@playwright/test";

const API_URL = process.env.API_URL || "https://api.viperai.io";

export async function purgeTestAccounts(request: APIRequestContext): Promise<void> {
  try {
    const loginResp = await request.post(`${API_URL}/api/auth/admin/login`, {
      data: { email: "admin@viperai.io", password: "Password123!" },
    });
    if (!loginResp.ok()) return;

    const { access_token } = await loginResp.json();
    await request.post(`${API_URL}/api/admin/purge-test-accounts`, {
      headers: { "X-Auth-Token": access_token },
    });
  } catch {
    // Cleanup is best-effort — don't fail tests if it doesn't work
  }
}
