export type BriefLang = 'en' | 'ar'
export type SignupResult = { ok: true } | { ok: false; reason: 'invalid' | 'network' }

/** Stub until the Render service exists: waits, then succeeds. Only this function changes later (a fetch to the API). */
export async function signup(email: string, briefLang: BriefLang): Promise<SignupResult> {
  void briefLang
  await new Promise((resolve) => setTimeout(resolve, 900))
  // Dev-only switch to test the error state: any email starting with "fail" simulates a network failure
  if (import.meta.env.DEV && email.startsWith('fail')) return { ok: false, reason: 'network' }
  return { ok: true }
}
