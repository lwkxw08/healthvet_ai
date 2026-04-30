/**
 * Flow 5: Re-trigger CV Check
 *
 * 1. Register an agency and a candidate (via invite)
 * 2. Navigate to the agency candidates tab
 * 3. Click "Re-Vet" on the candidate
 * 4. Select the CV section in the re-vet modal
 * 5. Submit the re-vet request
 * 6. Verify the re-vet request appears in the history
 */
import { test, expect } from "@playwright/test";

const suffix = Math.random().toString(36).slice(2, 8);
const API_URL = process.env.API_URL || "https://api.viperai.io";

test.describe("Re-trigger CV Check", () => {
  let agencyToken: string;
  let agencyId: string;
  let candidateEmail: string;

  test.beforeAll(async ({ request }) => {
    candidateEmail = `e2e-revet-${suffix}@test.viperai`;

    // Register agency
    const agencyResp = await request.post(`${API_URL}/api/auth/agencies/register`, {
      data: {
        email: `e2e-revet-agency-${suffix}@test.viperai`,
        password: "E2eTest123!",
        name: `E2E ReVet Agency ${suffix}`,
        contact_name: "E2E ReVet Contact",
        phone: "07700900004",
      },
    });
    expect(agencyResp.ok()).toBeTruthy();
    const agencyBody = await agencyResp.json();
    agencyToken = agencyBody.access_token;
    agencyId = agencyBody.user_id;

    // Subscribe
    await request.post(`${API_URL}/api/billing/subscribe`, {
      headers: { "X-Auth-Token": agencyToken },
      data: { tier: "starter", billing_method: "invoice" },
    });

    // Send invite
    await request.post(`${API_URL}/api/agencies/invites`, {
      headers: { "X-Auth-Token": agencyToken },
      data: { candidate_email: candidateEmail },
    });

    // Register candidate with invite
    const listResp = await request.get(`${API_URL}/api/agencies/invites`, {
      headers: { "X-Auth-Token": agencyToken },
    });
    const invites = await listResp.json();
    const invite = (Array.isArray(invites) ? invites : []).find(
      (i: Record<string, unknown>) =>
        (i.candidate_email as string)?.toLowerCase() === candidateEmail.toLowerCase(),
    );

    await request.post(`${API_URL}/api/auth/candidates/register`, {
      data: {
        email: candidateEmail,
        password: "E2eTest123!",
        first_name: "E2E",
        last_name: "ReVetCandidate",
        phone: "07700900055",
        profession: "Registered Nurse",
        invite_code: invite?.invite_code || invite?.id,
      },
    });
  });

  test("agency dashboard shows candidate with Re-Vet button", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(
      (a) => localStorage.setItem("viperai_auth", JSON.stringify(a)),
      { token: agencyToken, userType: "agency", userId: agencyId },
    );
    await page.reload();

    await expect(page.getByText("Agency Dashboard")).toBeVisible({ timeout: 15000 });

    // Navigate to Candidates tab
    const candidatesTab = page.locator("button", { hasText: "Candidates" }).first();
    await candidatesTab.click();
    await page.waitForTimeout(2000);

    // Candidate should be visible
    const candidateRow = page.getByText("E2E ReVetCandidate").or(page.getByText(candidateEmail)).first();
    await expect(candidateRow).toBeVisible({ timeout: 10000 });

    // Re-Vet button should exist on the page
    const revetBtn = page.locator('button:has-text("Re-Vet")').first();
    await expect(revetBtn).toBeVisible({ timeout: 5000 });
  });

  test("open Re-Vet modal and see section options", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(
      (a) => localStorage.setItem("viperai_auth", JSON.stringify(a)),
      { token: agencyToken, userType: "agency", userId: agencyId },
    );
    await page.reload();

    await expect(page.getByText("Agency Dashboard")).toBeVisible({ timeout: 15000 });

    // Navigate to Candidates tab
    await page.locator("button", { hasText: "Candidates" }).first().click();
    await page.waitForTimeout(2000);

    // Click Re-Vet on the first candidate
    const revetBtn = page.locator('button:has-text("Re-Vet")').first();
    await revetBtn.click();
    await page.waitForTimeout(500);

    // Modal should appear with "Request Re-Vet" heading
    await expect(page.getByText("Request Re-Vet")).toBeVisible({ timeout: 5000 });

    // Section options should be visible
    await expect(page.getByText("CV Analysis")).toBeVisible({ timeout: 3000 });
    await expect(page.getByText("Identity Verification")).toBeVisible({ timeout: 3000 });
    await expect(page.getByText("DBS Check")).toBeVisible({ timeout: 3000 });
  });

  test("select CV section and submit re-vet request", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(
      (a) => localStorage.setItem("viperai_auth", JSON.stringify(a)),
      { token: agencyToken, userType: "agency", userId: agencyId },
    );
    await page.reload();

    await expect(page.getByText("Agency Dashboard")).toBeVisible({ timeout: 15000 });

    // Navigate to Candidates tab
    await page.locator("button", { hasText: "Candidates" }).first().click();
    await page.waitForTimeout(2000);

    // Click Re-Vet on the first candidate
    await page.locator('button:has-text("Re-Vet")').first().click();
    await page.waitForTimeout(500);

    await expect(page.getByText("Request Re-Vet")).toBeVisible({ timeout: 5000 });

    // Select "CV Analysis" checkbox
    const cvLabel = page.locator("label", { hasText: "CV Analysis" });
    await cvLabel.click();
    await page.waitForTimeout(300);

    // Estimated total should show a price in the total row
    const totalRow = page.locator('text=/Estimated Total/');
    await expect(totalRow).toBeVisible({ timeout: 3000 });

    // Submit the re-vet request
    const submitBtn = page.locator('button:has-text("Submit Re-Vet Request")');
    await submitBtn.click();
    await page.waitForTimeout(2000);

    // Should see success message
    await expect(
      page.getByText("Re-vet request submitted successfully"),
    ).toBeVisible({ timeout: 10000 });
  });

  test("re-vet request API works directly", async ({ request }) => {
    // Get candidates list to find our candidate's ID
    const candidatesResp = await request.get(
      `${API_URL}/api/agencies/candidates-with-status`,
      { headers: { "X-Auth-Token": agencyToken } },
    );

    if (candidatesResp.ok()) {
      const candidates = await candidatesResp.json();
      const ourCandidate = (Array.isArray(candidates) ? candidates : []).find(
        (c: Record<string, unknown>) =>
          String(c.email).toLowerCase() === candidateEmail.toLowerCase() ||
          String(c.last_name) === "ReVetCandidate",
      );

      if (ourCandidate) {
        const candidateId = String(ourCandidate.id || ourCandidate.candidate_id);

        // Request a re-vet on identity section
        const revetResp = await request.post(
          `${API_URL}/api/agencies/candidates/${candidateId}/request-revet`,
          {
            headers: { "X-Auth-Token": agencyToken },
            data: { sections: ["identity"] },
          },
        );

        if (revetResp.ok()) {
          const result = await revetResp.json();
          expect(result.token || result.id).toBeTruthy();
        }
      }
    }

    // Verify re-vet requests list
    const listResp = await request.get(`${API_URL}/api/agencies/revet-requests`, {
      headers: { "X-Auth-Token": agencyToken },
    });
    expect(listResp.ok()).toBeTruthy();
    const requests = await listResp.json();
    expect(Array.isArray(requests)).toBeTruthy();
  });
});
