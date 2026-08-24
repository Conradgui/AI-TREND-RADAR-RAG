import { expect, test } from "@playwright/test";

test.setTimeout(90_000);

test.beforeEach(async ({ page }) => {
  await page.route("**/manifest.json", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ dates: [{ date: "2026-08-10", reports: ["ai-topic-radar"] }] }),
    }),
  );
  await page.route("**/digests/search-index.json", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ schema_version: 2, documents: [] }),
    }),
  );
  await page.route("**/digests/2026-08-10/ai-topic-radar.md", (route) =>
    route.fulfill({
      contentType: "text/markdown",
      body: "# Fixture report",
    }),
  );
});

test("source setup wizard generates safe GitHub configuration without collecting secrets", async ({
  page,
}) => {
  await page.goto("/#2026-08-10/ai-topic-radar", { waitUntil: "domcontentloaded" });
  await page.locator("#systemBtn").click();
  await page.getByRole("button", { name: "配置自动语料" }).click();

  const wizard = page.getByRole("region", { name: "自动语料配置向导" });
  await expect(wizard).toBeVisible();
  await expect(wizard).toContainText("不会读取或保存 Secret");
  await expect(wizard.locator('input[type="password"]')).toHaveCount(0);
  await expect(wizard.getByLabel("托管语料")).toBeChecked();

  await wizard.getByLabel("自维护语料").check();
  await wizard.getByLabel("GitHub 仓库").fill("example/radar-fork");
  await wizard.getByLabel("模型 Provider").selectOption("openai");
  await wizard.getByLabel("Product Hunt").selectOption("enabled");

  await expect(wizard.getByTestId("source-variables-output")).toContainText("CORPUS_MODE=self_managed");
  await expect(wizard.getByTestId("source-variables-output")).toContainText(
    "SELF_MANAGED_LLM_PROVIDER=openai",
  );
  await expect(wizard.getByTestId("source-yaml-output")).toContainText("product_hunt: enabled");
  await expect(wizard.getByTestId("required-secrets")).toContainText("OPENAI_API_KEY");
  await expect(wizard.getByTestId("required-secrets")).toContainText("PRODUCTHUNT_TOKEN");
  await expect(wizard).toContainText("尚未修改 GitHub");

  await expect(wizard.getByRole("link", { name: "打开 Variables 设置" })).toHaveAttribute(
    "href",
    "https://github.com/example/radar-fork/settings/variables/actions",
  );
  await expect(wizard.getByRole("link", { name: "打开 Secrets 设置" })).toHaveAttribute(
    "href",
    "https://github.com/example/radar-fork/settings/secrets/actions",
  );
});

test("hosted mode stays the low-effort default and does not request source configuration", async ({
  page,
}) => {
  await page.goto("/#2026-08-10/ai-topic-radar", { waitUntil: "domcontentloaded" });
  await page.locator("#systemBtn").click();
  await page.getByRole("button", { name: "配置自动语料" }).click();

  const wizard = page.getByRole("region", { name: "自动语料配置向导" });
  await expect(wizard.getByLabel("托管语料")).toBeChecked();
  await expect(wizard.getByTestId("hosted-mode-summary")).toContainText("无需新闻源或模型密钥");
  await expect(wizard.getByTestId("self-managed-fields")).toBeHidden();
});
