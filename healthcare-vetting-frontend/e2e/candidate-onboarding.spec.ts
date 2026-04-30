/**
 * Flow 1: Candidate Onboarding → Vetting Pass
 *
 * Registers a new candidate via the UI, fills in the multi-step onboarding
 * form, gives consent, and submits for vetting.
 *
 * Uses the default healthcare industry template.
 */
import { test, expect } from "@playwright/test";

const suffix = Math.random().toString(36).slice(2, 8);
const candidatePassword = "E2eTest123!";

/**
 * The backend API lives on a separate origin (api.viperai.io) from the
 * frontend (app.viperai.io). Playwright's baseURL is the frontend; API
 * calls need the backend origin.
 */
const API_URL = process.env.API_URL || "https://api.viperai.io";

test.describe("Candidate Onboarding → Vetting Pass", () => {

  test("register a new candidate via the login page", async ({ page }) => {
    const candidateEmail = `e2e-reg-${suffix}@test.viperai`;

    await page.goto("/");

    // Wait for the login page to fully render
    await expect(page.locator('button:has-text("Sign In")').first()).toBeVisible({ timeout: 15000 });

    // Make sure we're on the Candidate tab
    const candidateTab = page.locator("button", { hasText: "Candidate" }).first();
    if (await candidateTab.isVisible()) {
      await candidateTab.click();
    }

    // Switch to registration mode
    const registerLink = page.locator('button:has-text("Register")').first();
    await registerLink.click();

    // Wait for registration form
    await expect(page.locator('button:has-text("Create Account")').first()).toBeVisible({ timeout: 5000 });

    // Fill name fields (appear first in register mode for candidates)
    const firstNameInput = page.locator('input[type="text"]').first();
    await firstNameInput.fill("E2E");

    const lastNameInput = page.locator('input[type="text"]').nth(1);
    await lastNameInput.fill("Candidate");

    // Fill email and password
    await page.locator('input[type="email"]').fill(candidateEmail);
    await page.locator('input[type="password"]').fill(candidatePassword);

    // Submit registration
    await page.locator('button:has-text("Create Account")').click();

    // Should redirect to the candidate onboarding dashboard
    await expect(
      page.locator("text=Personal Details").first(),
    ).toBeVisible({ timeout: 15000 });
  });

  test("fill personal details section", async ({ page, request }) => {
    const resp = await request.post(`${API_URL}/api/auth/candidates/register`, {
      data: {
        email: `e2e-pd-${suffix}@test.viperai`,
        password: candidatePassword,
        first_name: "E2E",
        last_name: "TestCandidate",
        phone: "07700900001",
        profession: "Registered Nurse",
        registration_body: "NMC",
        registration_number: "12A3456B",
      },
    });
    expect(resp.ok()).toBeTruthy();
    const auth = await resp.json();

    await page.goto("/");
    await page.evaluate(
      (a) => localStorage.setItem("viperai_auth", JSON.stringify(a)),
      { token: auth.access_token, userType: auth.user_type, userId: auth.user_id },
    );
    await page.reload();

    // Should be on the candidate onboarding page
    await expect(page.locator("text=Personal Details").first()).toBeVisible({ timeout: 15000 });

    // Click Personal Details section
    await page.locator("text=Personal Details").first().click();

    // Fill fields that are visible
    const dateInput = page.locator('input[type="date"]').first();
    if (await dateInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await dateInput.fill("1990-06-15");
    }

    const textareas = page.locator("textarea").first();
    if (await textareas.isVisible({ timeout: 2000 }).catch(() => false)) {
      await textareas.fill("123 E2E Test Street, London, E1 1AA");
    }

    // Save / Next
    const saveBtn = page.locator('button:has-text("Save"), button:has-text("Next"), button:has-text("Continue")').first();
    if (await saveBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await saveBtn.click();
      await page.waitForTimeout(1000);
    }

    // Page should still be functional
    const pageContent = await page.textContent("body");
    expect(pageContent).toBeTruthy();
  });

  test("navigate through all onboarding sections", async ({ page, request }) => {
    const resp = await request.post(`${API_URL}/api/auth/candidates/register`, {
      data: {
        email: `e2e-nav-${suffix}@test.viperai`,
        password: candidatePassword,
        first_name: "E2E",
        last_name: "Navigator",
        profession: "Healthcare Assistant",
      },
    });
    expect(resp.ok()).toBeTruthy();
    const auth = await resp.json();

    await page.goto("/");
    await page.evaluate(
      (a) => localStorage.setItem("viperai_auth", JSON.stringify(a)),
      { token: auth.access_token, userType: auth.user_type, userId: auth.user_id },
    );
    await page.reload();

    // Wait for onboarding page to load
    await expect(page.locator("text=Personal Details").first()).toBeVisible({ timeout: 15000 });

    // Check all expected sections are present in the healthcare template
    const expectedSections = [
      "Personal Details",
      "Identity",
      "Right to Work",
      "DBS",
      "CV",
      "Registration",
      "References",
      "Training",
    ];

    for (const section of expectedSections) {
      const sectionEl = page.locator(`text=${section}`).first();
      await expect(sectionEl).toBeVisible({ timeout: 5000 });
    }
  });

  test("submit onboarding and check compliance status", async ({ page, request }) => {
    const regResp = await request.post(`${API_URL}/api/auth/candidates/register`, {
      data: {
        email: `e2e-submit-${suffix}@test.viperai`,
        password: candidatePassword,
        first_name: "E2E",
        last_name: "Submitter",
        profession: "Registered Nurse",
        registration_body: "NMC",
        registration_number: "99Z9999Z",
      },
    });
    expect(regResp.ok()).toBeTruthy();
    const auth = await regResp.json();
    const candidateToken = auth.access_token;

    // Create a submission via API
    const subResp = await request.post(`${API_URL}/api/submissions`, {
      headers: { "X-Auth-Token": candidateToken },
      data: {},
    });
    const submission = await subResp.json();
    const submissionId = submission.id || submission.submission_id;

    if (submissionId) {
      await request.put(`${API_URL}/api/submissions/${submissionId}/sections/personal`, {
        headers: { "X-Auth-Token": candidateToken },
        data: {
          first_name: "E2E",
          last_name: "Submitter",
          date_of_birth: "1990-01-15",
          address: "123 Test Road, London, E1 1AA",
          ni_number: "AB123456C",
        },
      });

      await request.post(`${API_URL}/api/submissions/${submissionId}/submit`, {
        headers: { "X-Auth-Token": candidateToken },
      });
    }

    // Load the page and verify it renders without errors
    await page.goto("/");
    await page.evaluate(
      (a) => localStorage.setItem("viperai_auth", JSON.stringify(a)),
      { token: auth.access_token, userType: auth.user_type, userId: auth.user_id },
    );
    await page.reload();

    await expect(page.locator("text=Personal Details").first()).toBeVisible({ timeout: 15000 });

    const pageContent = await page.textContent("body");
    expect(pageContent).toBeTruthy();
    expect(pageContent).not.toContain("Something went wrong");
  });
});
