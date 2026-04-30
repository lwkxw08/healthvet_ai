/**
 * Auth helpers for Playwright E2E tests.
 *
 * Uses the API directly (not the UI) for speed — the login UI itself is
 * tested via the candidate onboarding flow.
 */
import { type Page, type APIRequestContext } from "@playwright/test";

/** Register a new candidate via the API and inject the token into localStorage. */
export async function registerCandidate(
  request: APIRequestContext,
  baseURL: string,
  overrides: Partial<{
    email: string;
    password: string;
    first_name: string;
    last_name: string;
    phone: string;
    profession: string;
    registration_number: string;
    registration_body: string;
    invite_code: string;
  }> = {},
) {
  const suffix = Math.random().toString(36).slice(2, 8);
  const data = {
    email: `e2e-cand-${suffix}@test.viperai`,
    password: "E2eTest123!",
    first_name: "E2E",
    last_name: "Candidate",
    phone: "07700900001",
    profession: "Nurse",
    registration_number: "",
    registration_body: "",
    ...overrides,
  };

  const resp = await request.post(`${baseURL}/api/auth/candidates/register`, {
    data,
  });
  const body = await resp.json();
  return {
    token: body.access_token as string,
    userId: body.user_id as string,
    userType: body.user_type as string,
    email: data.email,
    password: data.password,
  };
}

/** Register a new agency via the API and return its token. */
export async function registerAgency(
  request: APIRequestContext,
  baseURL: string,
  overrides: Partial<{
    email: string;
    password: string;
    name: string;
    contact_name: string;
    phone: string;
    plan: string;
  }> = {},
) {
  const suffix = Math.random().toString(36).slice(2, 8);
  const data = {
    email: `e2e-agency-${suffix}@test.viperai`,
    password: "E2eTest123!",
    name: `E2E Agency ${suffix}`,
    contact_name: "E2E Contact",
    phone: "07700900002",
    plan: "starter",
    ...overrides,
  };

  const resp = await request.post(`${baseURL}/api/auth/agencies/register`, {
    data,
  });
  const body = await resp.json();
  return {
    token: body.access_token as string,
    userId: body.user_id as string,
    userType: body.user_type as string,
    email: data.email,
    password: data.password,
    name: data.name,
  };
}

/** Log in via the API and return the token. */
export async function loginAdmin(
  request: APIRequestContext,
  baseURL: string,
  email = "admin@viperai.io",
  password = "Password123!",
) {
  const resp = await request.post(`${baseURL}/api/auth/admin/login`, {
    data: { email, password },
  });
  const body = await resp.json();
  return {
    token: body.access_token as string,
    userId: body.user_id as string,
    userType: body.user_type as string,
  };
}

/** Inject auth state into localStorage so the page picks it up on load. */
export async function injectAuth(
  page: Page,
  baseURL: string,
  auth: { token: string; userType: string; userId: string },
) {
  await page.goto(baseURL);
  await page.evaluate(
    ({ token, userType, userId }) => {
      localStorage.setItem(
        "viperai_auth",
        JSON.stringify({ token, userType, userId }),
      );
    },
    { token: auth.token, userType: auth.userType, userId: auth.userId },
  );
  await page.reload();
}
