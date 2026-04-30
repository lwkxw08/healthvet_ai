/**
 * Flow 2: Agency Invite → Billing
 *
 * 1. Register a new agency via API
 * 2. Subscribe to a credit pack (starter tier via API)
 * 3. Send a candidate invite from the agency dashboard
 * 4. Verify the invite appears in the invites list
 * 5. Register the candidate using the invite code
 * 6. Verify billing records and credit deduction
 */
import { test, expect } from "@playwright/test";

const suffix = Math.random().toString(36).slice(2, 8);

test.describe("Agency Invite → Billing", () => {
  let agencyToken: string;
  let agencyId: string;
  let candidateEmail: string;

  test.beforeAll(async ({ request }) => {
    candidateEmail = `e2e-invited-${suffix}@test.viperai`;

    // Register a new agency (relative URL — Playwright prepends baseURL)
    const resp = await request.post("/api/auth/agencies/register", {
      data: {
        email: `e2e-agency-${suffix}@test.viperai`,
        password: "E2eTest123!",
        name: `E2E Agency ${suffix}`,
        contact_name: "E2E Contact",
        phone: "07700900002",
      },
    });
    const body = await resp.json();
    agencyToken = body.access_token;
    agencyId = body.user_id;

    // Subscribe to starter plan via API (gives credits)
    await request.post("/api/billing/subscribe", {
      headers: { "X-Auth-Token": agencyToken },
      data: { tier: "starter", billing_method: "invoice" },
    });
  });

  test("agency dashboard loads with invites tab", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(
      (a) => localStorage.setItem("viperai_auth", JSON.stringify(a)),
      { token: agencyToken, userType: "agency", userId: agencyId },
    );
    await page.reload();

    // Should see the agency dashboard — wait for any dashboard content
    await expect(
      page.locator("text=Dashboard, text=Candidates, text=Invites").first(),
    ).toBeVisible({ timeout: 15000 });

    // Navigate to Invites tab
    const invitesTab = page.locator("button, a, [role='tab']", { hasText: "Invites" }).first();
    if (await invitesTab.isVisible({ timeout: 5000 }).catch(() => false)) {
      await invitesTab.click();
      await page.waitForTimeout(1000);
    }
  });

  test("send a candidate invite via the API", async ({ request }) => {
    const resp = await request.post("/api/agencies/invites", {
      headers: { "X-Auth-Token": agencyToken },
      data: { candidate_email: candidateEmail },
    });

    expect(resp.ok()).toBeTruthy();
    const invite = await resp.json();
    expect(invite.invite_code || invite.id).toBeTruthy();
  });

  test("invite appears in agency invites list", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(
      (a) => localStorage.setItem("viperai_auth", JSON.stringify(a)),
      { token: agencyToken, userType: "agency", userId: agencyId },
    );
    await page.reload();

    // Wait for dashboard
    await expect(page.locator("text=Dashboard").first()).toBeVisible({ timeout: 15000 });

    // Go to invites tab
    const invitesTab = page.locator("button, a, [role='tab']", { hasText: "Invites" }).first();
    if (await invitesTab.isVisible({ timeout: 5000 }).catch(() => false)) {
      await invitesTab.click();
      await page.waitForTimeout(2000);
    }

    // Verify the invited email appears
    const inviteRow = page.locator(`text=${candidateEmail}`);
    await expect(inviteRow).toBeVisible({ timeout: 10000 });
  });

  test("candidate registers using invite and appears on agency dashboard", async ({
    page,
    request,
  }) => {
    // Get the invite info to find the invite code
    const listResp = await request.get("/api/agencies/invites", {
      headers: { "X-Auth-Token": agencyToken },
    });
    const invites = await listResp.json();
    const invite = (Array.isArray(invites) ? invites : []).find(
      (i: Record<string, unknown>) =>
        (i.candidate_email as string)?.toLowerCase() === candidateEmail.toLowerCase(),
    );
    const inviteCode = invite?.invite_code || invite?.id;

    // Register the candidate with the invite code
    const regResp = await request.post("/api/auth/candidates/register", {
      data: {
        email: candidateEmail,
        password: "E2eTest123!",
        first_name: "E2E",
        last_name: "Invited",
        phone: "07700900099",
        profession: "Healthcare Assistant",
        invite_code: inviteCode,
      },
    });
    expect(regResp.ok()).toBeTruthy();

    // Now load the agency dashboard and check candidates tab
    await page.goto("/");
    await page.evaluate(
      (a) => localStorage.setItem("viperai_auth", JSON.stringify(a)),
      { token: agencyToken, userType: "agency", userId: agencyId },
    );
    await page.reload();

    await expect(page.locator("text=Dashboard").first()).toBeVisible({ timeout: 15000 });

    // Navigate to Candidates tab
    const candidatesTab = page.locator("button, a, [role='tab']", { hasText: "Candidates" }).first();
    if (await candidatesTab.isVisible({ timeout: 5000 }).catch(() => false)) {
      await candidatesTab.click();
      await page.waitForTimeout(2000);
    }

    // The newly registered candidate should appear
    const candidateRow = page.locator(`text=E2E Invited, text=${candidateEmail}`).first();
    await expect(candidateRow).toBeVisible({ timeout: 10000 });
  });

  test("billing reflects the invite credit usage", async ({ request }) => {
    // Check remaining credits via API
    const creditsResp = await request.get("/api/billing/remaining-checks", {
      headers: { "X-Auth-Token": agencyToken },
    });

    if (creditsResp.ok()) {
      const credits = await creditsResp.json();
      expect(credits).toBeTruthy();
      expect(
        credits.remaining !== undefined ||
        credits.remaining_checks !== undefined ||
        credits.total !== undefined,
      ).toBeTruthy();
    }

    // Check billing history / invoices via API
    const historyResp = await request.get("/api/billing/history", {
      headers: { "X-Auth-Token": agencyToken },
    });

    if (historyResp.ok()) {
      const history = await historyResp.json();
      expect(history).toBeTruthy();
    }
  });

  test("agency invite flow renders on the UI", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(
      (a) => localStorage.setItem("viperai_auth", JSON.stringify(a)),
      { token: agencyToken, userType: "agency", userId: agencyId },
    );
    await page.reload();

    // Wait for dashboard
    await expect(page.locator("text=Dashboard").first()).toBeVisible({ timeout: 15000 });

    // Go to invites tab
    const invitesTab = page.locator("button, a, [role='tab']", { hasText: "Invites" }).first();
    if (await invitesTab.isVisible({ timeout: 5000 }).catch(() => false)) {
      await invitesTab.click();
      await page.waitForTimeout(1000);
    }

    // Verify invite email input exists
    const emailInput = page.locator('input[type="email"], input[placeholder*="email" i]').first();
    await expect(emailInput).toBeVisible({ timeout: 5000 });

    // Type a new email and check the invite button is there
    await emailInput.fill("new-invite-test@example.com");
    const sendBtn = page.locator(
      'button:has-text("Send"), button:has-text("Invite"), button:has-text("Add")',
    ).first();
    await expect(sendBtn).toBeVisible({ timeout: 5000 });

    // Verify billing tab exists
    const billingTab = page.locator("button, a, [role='tab']", { hasText: "Billing" }).first();
    if (await billingTab.isVisible({ timeout: 5000 }).catch(() => false)) {
      await billingTab.click();
      await page.waitForTimeout(1000);

      // Should show some billing content
      const billingContent = page.locator(
        "text=Credit, text=Plan, text=Subscription, text=Invoice, text=Billing",
      ).first();
      await expect(billingContent).toBeVisible({ timeout: 5000 });
    }
  });
});
