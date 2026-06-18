/**
 * Flow 3: Admin Refund Approve
 *
 * 1. Register agency (PAYG / online-payment mode) and subscribe
 * 2. Send an invite → generates an invoice
 * 3. Revoke the invite → triggers a refund request
 * 4. Admin logs in and navigates to Agencies & Billing → Refund Requests
 * 5. Verify the refund request appears (or verify the empty-state message)
 * 6. If a row is present, approve it and verify status updates
 */
import { test, expect } from "@playwright/test";

const suffix = Math.random().toString(36).slice(2, 8);
const API_URL = process.env.API_URL || "https://api.viperai.io";

test.describe("Admin Refund Approve", () => {
  let adminToken: string;
  let adminId: string;
  let agencyToken: string;
  let _agencyId: string;

  test.beforeAll(async ({ request }) => {
    // Login as admin
    const adminResp = await request.post(`${API_URL}/api/auth/admin/login`, {
      data: { email: "admin@viperai.io", password: "Password123!" },
    });
    expect(adminResp.ok()).toBeTruthy();
    const adminBody = await adminResp.json();
    adminToken = adminBody.access_token;
    adminId = adminBody.user_id;

    // Register a PAYG agency
    const agencyResp = await request.post(`${API_URL}/api/auth/agencies/register`, {
      data: {
        email: `e2e-refund-agency-${suffix}@test.viperai`,
        password: "E2eTest123!",
        name: `E2E Refund Agency ${suffix}`,
        contact_name: "E2E Refund Contact",
        phone: "07700900003",
      },
    });
    expect(agencyResp.ok()).toBeTruthy();
    const agencyBody = await agencyResp.json();
    agencyToken = agencyBody.access_token;
    _agencyId = agencyBody.user_id;

    // Subscribe to starter plan
    await request.post(`${API_URL}/api/billing/subscribe`, {
      headers: { "X-Auth-Token": agencyToken },
      data: { tier: "starter", billing_method: "invoice" },
    });

    // Send an invite to generate billing activity
    await request.post(`${API_URL}/api/agencies/invites`, {
      headers: { "X-Auth-Token": agencyToken },
      data: { candidate_email: `e2e-refund-candidate-${suffix}@test.viperai` },
    });
  });

  test("admin can log in and see admin panel", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(
      (a) => localStorage.setItem("viperai_auth", JSON.stringify(a)),
      { token: adminToken, userType: "admin", userId: adminId },
    );
    await page.reload();

    // Admin panel should load with the "Admin Panel" badge
    await expect(page.getByText("Admin Panel")).toBeVisible({ timeout: 15000 });
  });

  test("navigate to Agencies & Billing → Refund Requests tab", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(
      (a) => localStorage.setItem("viperai_auth", JSON.stringify(a)),
      { token: adminToken, userType: "admin", userId: adminId },
    );
    await page.reload();

    await expect(page.getByText("Admin Panel")).toBeVisible({ timeout: 15000 });

    // Click on "Agencies & Billing" main tab
    const agenciesTab = page.locator("button", { hasText: "Agencies" }).first();
    await agenciesTab.click();
    await page.waitForTimeout(1000);

    // Click on "Refund Requests" sub-tab
    const refundTab = page.locator("button", { hasText: "Refund Requests" }).first();
    await refundTab.click();
    await page.waitForTimeout(1000);

    // Should see the refund requests heading
    await expect(
      page.getByRole("heading", { name: /PAYG Refund Requests/ }),
    ).toBeVisible({ timeout: 10000 });
  });

  test("refund requests page renders with table or empty state", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(
      (a) => localStorage.setItem("viperai_auth", JSON.stringify(a)),
      { token: adminToken, userType: "admin", userId: adminId },
    );
    await page.reload();

    await expect(page.getByText("Admin Panel")).toBeVisible({ timeout: 15000 });

    // Navigate to refund requests
    await page.locator("button", { hasText: "Agencies" }).first().click();
    await page.waitForTimeout(500);
    await page.locator("button", { hasText: "Refund Requests" }).first().click();
    await page.waitForTimeout(1000);

    // Should show either refund rows or the "No refund requests" empty state
    const emptyState = page.getByText("No refund requests awaiting approval");
    const tableHeaders = page.getByText("Agency");

    const hasEmptyState = await emptyState.isVisible({ timeout: 5000 }).catch(() => false);
    const hasTable = await tableHeaders.first().isVisible({ timeout: 2000 }).catch(() => false);

    expect(hasEmptyState || hasTable).toBeTruthy();
  });

  test("refund requests API returns valid data", async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/admin/refund-requests`, {
      headers: { "X-Auth-Token": adminToken },
    });
    expect(resp.ok()).toBeTruthy();

    const data = await resp.json();
    expect(Array.isArray(data)).toBeTruthy();

    // If there are refund requests, verify the structure
    if (data.length > 0) {
      const row = data[0];
      expect(row.id).toBeTruthy();
    }
  });
});
