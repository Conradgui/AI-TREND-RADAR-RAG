import { expect, test } from '@playwright/test'

test('search opens a stable item detail route and restores it through browser history', async ({ page }) => {
  await page.goto('/#2026-08-05/ai-topic-radar')

  const search = page.getByRole('searchbox', { name: '搜索报告条目' })
  await expect(search).toBeVisible()
  await search.fill('量子香蕉协议')
  await expect(page.locator('#searchResults .search-result')).toHaveCount(0)
  await expect(page.locator('#searchResults .search-empty')).toBeVisible()

  await search.fill('opneai')
  await expect(page.locator('#searchResults .search-result').first()).toBeVisible()

  await search.fill('Open AI')

  const results = page.locator('#searchResults .search-result')
  await expect(results.first()).toBeVisible()
  await expect(page.locator('#searchStatus')).toContainText('已识别为 OpenAI')
  await results.first().click()

  await expect(page).toHaveURL(/#\d{4}-\d{2}-\d{2}\/ai-topic-radar\/item\/[a-f0-9]{32}$/)
  const detailTitle = page.locator('.item-detail h1')
  await expect(detailTitle).toBeVisible()
  const title = await detailTitle.textContent()
  await expect(page.getByRole('link', { name: '查看原始来源 ↗' })).toBeVisible()

  await page.reload()
  await expect(page.locator('.item-detail h1')).toHaveText(title || '')

  await page.goBack()
  await expect(page.locator('.md')).toBeVisible()
  await page.goForward()
  await expect(page.locator('.item-detail h1')).toHaveText(title || '')
})

test('report positioning is offered only for an explicit producer target', async ({ page }) => {
  const occurrenceId = 'f'.repeat(32)
  await page.route('**/digests/search-index.json', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
      schema_version: 1,
      id_scheme: 'sd-v1',
      documents: [{
        occurrence_id: occurrenceId,
        item_anchor: `item-${occurrenceId}`,
        date: '2026-08-05',
        report_id: 'ai-topic-radar',
        title: 'Explicit Report Target',
        normalized_title: 'explicit report target',
        summary: 'Fixture summary',
        source: 'Fixture Source',
        category: 'Fixture',
        action: '验证',
        score: 100,
        tags: [],
        aliases: [],
        display_fields: {},
        external_url: 'https://example.com/source',
        report_target: { report_id: 'ai-topic-radar', anchor_id: 'fixture-entry-1' },
      }],
    }),
  }))
  await page.route('**/digests/2026-08-05/ai-topic-radar.md', (route) => route.fulfill({
    contentType: 'text/markdown',
    body: '# Fixture report\n\n<div id="fixture-entry-1">Mapped report entry</div>',
  }))

  await page.goto('/#2026-08-05/ai-topic-radar')
  await page.getByRole('searchbox', { name: '搜索报告条目' }).fill('Explicit Report Target')
  await page.locator('#searchResults .search-result').click()
  await page.getByRole('button', { name: '在日报中定位' }).click()

  await expect(page).toHaveURL(/#2026-08-05\/ai-topic-radar$/)
  await expect(page.locator('#fixture-entry-1')).toHaveClass(/search-hit/)
})
