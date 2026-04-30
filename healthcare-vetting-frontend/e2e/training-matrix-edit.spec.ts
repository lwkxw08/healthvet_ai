/**
 * Flow 4: Training Matrix Edit
 *
 * 1. Admin logs in and navigates to Settings → Training Matrix
 * 2. Verify existing courses load from the catalogue
 * 3. Add a new training course via the UI
 * 4. Verify the course appears in the list
 * 5. Edit the course name
 * 6. Delete the course and verify removal
 */
import { test, expect } from "@playwright/test";

const suffix = Math.random().toString(36).slice(2, 8);
const API_URL = process.env.API_URL || "https://api.viperai.io";

test.describe("Training Matrix Edit", () => {
  let adminToken: string;
  let adminId: string;
  let healthcareTemplateId: string;

  test.beforeAll(async ({ request }) => {
    // Login as admin
    const adminResp = await request.post(`${API_URL}/api/auth/admin/login`, {
      data: { email: "admin@viperai.io", password: "Password123!" },
    });
    expect(adminResp.ok()).toBeTruthy();
    const adminBody = await adminResp.json();
    adminToken = adminBody.access_token;
    adminId = adminBody.user_id;

    // Get the Healthcare template ID
    const templatesResp = await request.get(`${API_URL}/api/admin/industry-templates`, {
      headers: { "X-Auth-Token": adminToken },
    });
    const templates = await templatesResp.json();
    const templateList = Array.isArray(templates) ? templates : templates.templates || [];
    const healthcare = templateList.find(
      (t: Record<string, unknown>) => String(t.name).includes("Healthcare"),
    );
    healthcareTemplateId = healthcare?.id || templateList[0]?.id;
  });

  test("admin navigates to Settings → Training Matrix", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(
      (a) => localStorage.setItem("viperai_auth", JSON.stringify(a)),
      { token: adminToken, userType: "admin", userId: adminId },
    );
    await page.reload();

    await expect(page.getByText("Admin Panel")).toBeVisible({ timeout: 15000 });

    // Click on Settings main tab
    const settingsTab = page.locator("button", { hasText: "Settings" }).first();
    await settingsTab.click();
    await page.waitForTimeout(1000);

    // Click on Training Matrix sub-tab
    const trainingTab = page.locator("button", { hasText: "Training Matrix" }).first();
    await trainingTab.click();
    await page.waitForTimeout(1000);

    // Should see the training matrix panel
    await expect(
      page.getByText("Training Course Catalogue").or(page.getByText("Training Matrix")).first(),
    ).toBeVisible({ timeout: 10000 });
  });

  test("training courses list loads from the API", async ({ request }) => {
    const resp = await request.get(
      `${API_URL}/api/training-courses?industry_template_id=${healthcareTemplateId}`,
      { headers: { "X-Auth-Token": adminToken } },
    );
    expect(resp.ok()).toBeTruthy();

    const data = await resp.json();
    const courses = data.courses || [];
    expect(courses.length).toBeGreaterThan(0);
  });

  test("create a new training course via API", async ({ request }) => {
    const courseName = `E2E Test Course ${suffix}`;

    const resp = await request.post(`${API_URL}/api/admin/training-courses`, {
      headers: { "X-Auth-Token": adminToken },
      data: {
        industry_template_id: healthcareTemplateId,
        name: courseName,
        aliases: [],
        category: "mandatory",
        description: "E2E test course for automated testing",
        default_validity_months: 12,
        is_mandatory: true,
        is_active: true,
        sort_order: 999,
      },
    });
    expect(resp.ok()).toBeTruthy();

    const course = await resp.json();
    expect(course.id).toBeTruthy();
    expect(course.name).toBe(courseName);
  });

  test("new course appears in training courses list", async ({ request }) => {
    const resp = await request.get(
      `${API_URL}/api/training-courses?industry_template_id=${healthcareTemplateId}&include_inactive=true`,
      { headers: { "X-Auth-Token": adminToken } },
    );
    expect(resp.ok()).toBeTruthy();

    const data = await resp.json();
    const courses = data.courses || [];
    const e2eCourse = courses.find(
      (c: Record<string, unknown>) => String(c.name).includes(`E2E Test Course ${suffix}`),
    );
    expect(e2eCourse).toBeTruthy();
  });

  test("update the training course via API", async ({ request }) => {
    // Find the course first
    const listResp = await request.get(
      `${API_URL}/api/training-courses?industry_template_id=${healthcareTemplateId}&include_inactive=true`,
      { headers: { "X-Auth-Token": adminToken } },
    );
    const data = await listResp.json();
    const courses = data.courses || [];
    const e2eCourse = courses.find(
      (c: Record<string, unknown>) => String(c.name).includes(`E2E Test Course ${suffix}`),
    );
    expect(e2eCourse).toBeTruthy();

    // Update the course
    const updateResp = await request.patch(
      `${API_URL}/api/admin/training-courses/${e2eCourse.id}`,
      {
        headers: { "X-Auth-Token": adminToken },
        data: {
          name: `E2E Updated Course ${suffix}`,
          description: "Updated by e2e test",
          default_validity_months: 24,
        },
      },
    );
    expect(updateResp.ok()).toBeTruthy();

    const updated = await updateResp.json();
    expect(updated.name).toBe(`E2E Updated Course ${suffix}`);
  });

  test("delete the training course via API", async ({ request }) => {
    // Find the course
    const listResp = await request.get(
      `${API_URL}/api/training-courses?industry_template_id=${healthcareTemplateId}&include_inactive=true`,
      { headers: { "X-Auth-Token": adminToken } },
    );
    const data = await listResp.json();
    const courses = data.courses || [];
    const e2eCourse = courses.find(
      (c: Record<string, unknown>) => String(c.name).includes(`E2E Updated Course ${suffix}`),
    );
    expect(e2eCourse).toBeTruthy();

    // Delete it
    const delResp = await request.delete(
      `${API_URL}/api/admin/training-courses/${e2eCourse.id}`,
      { headers: { "X-Auth-Token": adminToken } },
    );
    expect(delResp.ok()).toBeTruthy();

    // Verify it's gone
    const verifyResp = await request.get(
      `${API_URL}/api/training-courses?industry_template_id=${healthcareTemplateId}`,
      { headers: { "X-Auth-Token": adminToken } },
    );
    const verifyData = await verifyResp.json();
    const remaining = (verifyData.courses || []).find(
      (c: Record<string, unknown>) => String(c.name).includes(`E2E Updated Course ${suffix}`),
    );
    expect(remaining).toBeFalsy();
  });
});
