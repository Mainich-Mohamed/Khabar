// Cloudflare Worker `khabar-trigger`: starts the Khabar digest on GitHub Actions on time
// (GitHub's own cron ran 2-3 hours late).
//
// Deployed by hand: paste this file into the Worker's editor in the Cloudflare dashboard.
//   Cron trigger:  0 7,16,22 * * *   (UTC)
//   GITHUB_TOKEN:  secret, fine-grained token for this repo only, "Actions: Read and write"
//   COMMAND:       optional text variable, defaults to "run" ("check-feeds" for a test without email)
const DISPATCH_URL =
  "https://api.github.com/repos/Mainich-Mohamed/Khabar/actions/workflows/digest.yml/dispatches";

export default {
  async scheduled(controller, env, ctx) {
    const res = await fetch(DISPATCH_URL, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "khabar-trigger",          // GitHub rejects API calls without one
      },
      // COMMAND lets us test with check-feeds (no email) before switching to run
      body: JSON.stringify({ ref: "main", inputs: { command: env.COMMAND || "run" } }),
    });
    if (!res.ok) {
      // Throwing marks this cron event as failed in the Worker's logs
      throw new Error(`GitHub dispatch failed: ${res.status} ${await res.text()}`);
    }
  },

  // No public URL can start a digest
  async fetch() {
    return new Response("Not found", { status: 404 });
  },
};
