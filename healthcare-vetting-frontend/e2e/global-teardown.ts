/**
 * Global teardown — runs once after ALL test files complete.
 * Purges all @test.viperai accounts from the database.
 */

const API_URL = process.env.API_URL || "https://api.viperai.io";

async function globalTeardown() {
  try {
    const loginResp = await fetch(`${API_URL}/api/auth/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "admin@viperai.io", password: "Password123!" }),
    });
    if (!loginResp.ok) return;

    const { access_token } = await loginResp.json();
    const purgeResp = await fetch(`${API_URL}/api/admin/purge-test-accounts`, {
      method: "POST",
      headers: { "X-Auth-Token": access_token, "Content-Type": "application/json" },
    });
    if (purgeResp.ok) {
      const result = await purgeResp.json();
      console.log(`[teardown] Purged ${result.candidates_deleted} test candidates and ${result.agencies_deleted} test agencies`);
    }
  } catch {
    // Best-effort cleanup
  }
}

export default globalTeardown;
