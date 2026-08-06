/** @vitest-environment node */
import { describe, expect, it } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execSync } from "node:child_process";

const SKIP = process.env.SKIP_GITHUB_INSTALL_TESTS === "1";

describe.skipIf(SKIP)("github install smoke", () => {
  it("installs @ollie/integrations-openai-agents from GitHub tag", () => {
    const dir = mkdtempSync(join(tmpdir(), "ollie-openai-ts-install-"));
    try {
      execSync("npm init -y", { cwd: dir, stdio: "ignore" });
      execSync(
        'npm install "github:varunnaganathan/ollie-integrations#openai-agents-ts-v0.2.1:openai-agents-ts" --no-save',
        { cwd: dir, stdio: "pipe", timeout: 300_000 },
      );
      execSync('node -e "require(\\"@ollie/integrations-openai-agents\\"); console.log(\\"ok\\")"', {
        cwd: dir,
        stdio: "pipe",
      });
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  }, 360_000);
});
