import { expect, test } from '@playwright/test'

test('search filters expose loading state and browse indexed items without a keyword', async ({ page }) => {
  let releaseIndex!: () => void
  const indexGate = new Promise<void>((resolve) => {
    releaseIndex = resolve
  })
  await page.route('**/digests/search-index.json', async (route) => {
    await indexGate
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        schema_version: 2,
        id_scheme: 'atr-v1',
        documents: [
          {
            occurrence_id: 'ATR-20260812-A1B2C3',
            content_id: 'content-filter-1',
            item_anchor: 'item-ATR-20260812-A1B2C3',
            date: '2026-08-12',
            report_id: 'ai-topic-radar',
            title: 'OpenAI Filter Target',
            normalized_title: 'openai filter target',
            summary: 'Recent model release',
            source: 'OpenAI',
            category: '模型与技术突破',
            action: '深挖',
            score: 98,
            tags: [],
            aliases: [],
            display_fields: {},
          },
          {
            occurrence_id: 'ATR-20260701-D4E5F6',
            content_id: 'content-filter-2',
            item_anchor: 'item-ATR-20260701-D4E5F6',
            date: '2026-07-01',
            report_id: 'ai-topic-radar',
            title: 'Older OpenAI Item',
            normalized_title: 'older openai item',
            summary: 'Older item outside the seven-day window',
            source: 'OpenAI',
            category: '模型与技术突破',
            action: '关注',
            score: 80,
            tags: [],
            aliases: [],
            display_fields: {},
          },
          {
            occurrence_id: 'ATR-20260812-ABCDEF',
            content_id: 'content-filter-3',
            item_anchor: 'item-ATR-20260812-ABCDEF',
            date: '2026-08-12',
            report_id: 'ai-topic-radar',
            title: 'Anthropic Same-Day Noise',
            normalized_title: 'anthropic same day noise',
            summary: 'Same date and category, wrong source',
            source: 'Anthropic',
            category: '模型与技术突破',
            action: '关注',
            score: 95,
            tags: [],
            aliases: [],
            display_fields: {},
          },
          {
            occurrence_id: 'ATR-20260812-123ABC',
            content_id: 'content-filter-4',
            item_anchor: 'item-ATR-20260812-123ABC',
            date: '2026-08-12',
            report_id: 'ai-topic-radar',
            title: 'OpenAI Same-Day Category Noise',
            normalized_title: 'openai same day category noise',
            summary: 'Same date and source, wrong category',
            source: 'OpenAI',
            category: '企业落地与行业应用',
            action: '关注',
            score: 94,
            tags: [],
            aliases: [],
            display_fields: {},
          },
        ],
      }),
    })
  })

  await page.goto('/#2026-08-12/ai-topic-radar')
  const period = page.getByLabel('时间范围')
  const source = page.getByLabel('来源')
  const category = page.getByLabel('分类')
  const clearFilters = page.getByRole('button', { name: '清除所有筛选' })
  await expect(period).toBeDisabled()
  await expect(source).toBeDisabled()
  await expect(category).toBeDisabled()
  await expect(clearFilters).toBeDisabled()
  await expect(page.locator('#searchStatus')).toContainText('条目索引准备中')

  releaseIndex()
  await expect(period).toBeEnabled()
  await expect(source).toBeEnabled()
  await expect(category).toBeEnabled()
  await expect(source.locator('option')).toHaveText(['全部来源', 'Anthropic', 'OpenAI'])
  await expect(category.locator('option')).toHaveText(['全部分类', '企业落地与行业应用', '模型与技术突破'])

  await period.selectOption('7')
  await source.selectOption('OpenAI')
  await category.selectOption('模型与技术突破')
  await expect(clearFilters).toBeEnabled()
  await expect(page.locator('#searchStatus')).toContainText('筛选到 1 个条目')
  await expect(page.locator('#searchResults .search-result-title')).toHaveText('OpenAI Filter Target')

  await clearFilters.click()
  await expect(period).toHaveValue('all')
  await expect(source).toHaveValue('')
  await expect(category).toHaveValue('')
  await expect(clearFilters).toBeDisabled()
  await expect(page.locator('#searchStatus')).toContainText('筛选到 4 个条目')

  const search = page.getByRole('searchbox', { name: '搜索报告条目' })
  await search.fill('OpenAI')
  await expect(page.locator('#searchResults .search-result')).toHaveCount(3)
  await period.selectOption('7')
  await source.selectOption('OpenAI')
  await category.selectOption('模型与技术突破')
  await expect(page.locator('#searchResults .search-result')).toHaveCount(1)

  await clearFilters.click()
  await expect(search).toHaveValue('OpenAI')
  await expect(page.locator('#searchResults .search-result')).toHaveCount(3)

  await search.fill('')
  await period.selectOption('7')
  await source.selectOption('OpenAI')
  await category.selectOption('模型与技术突破')

  await page.locator('#searchResults .search-result').click()
  await expect(page).toHaveURL(/#2026-08-12\/ai-topic-radar\/item\/ATR-20260812-A1B2C3$/)
  await page.reload()
  await expect(page.locator('.item-detail h1')).toHaveText('OpenAI Filter Target')
})

test('search filters stay disabled and explain an index loading failure', async ({ page }) => {
  await page.route('**/digests/search-index.json', (route) => route.fulfill({ status: 503 }))
  await page.goto('/#2026-08-10/ai-topic-radar')

  await expect(page.getByLabel('时间范围')).toBeDisabled()
  await expect(page.getByLabel('来源')).toBeDisabled()
  await expect(page.getByLabel('分类')).toBeDisabled()
  await expect(page.getByRole('button', { name: '清除所有筛选' })).toBeDisabled()
  await expect(page.locator('#searchStatus')).toContainText('条目索引不可用：HTTP 503')
})

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

  await expect(page).toHaveURL(/#\d{4}-\d{2}-\d{2}\/ai-topic-radar\/item\/ATR-\d{8}-[A-F0-9]{6}$/)
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
  const occurrenceId = 'ATR-20260805-F1A2B3'
  await page.route('**/digests/search-index.json', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
      schema_version: 2,
      id_scheme: 'atr-v1',
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

test('legacy item bookmarks resolve to the same ATR item across navigation and reload', async ({ page }) => {
  const occurrenceId = 'ATR-20260812-A1B2C3'
  const legacyId = 'a'.repeat(32)
  await page.route('**/digests/search-index.json', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
      schema_version: 2,
      id_scheme: 'atr-v1',
      documents: [{
        occurrence_id: occurrenceId,
        legacy_ids: [legacyId],
        item_anchor: `item-${occurrenceId}`,
        date: '2026-08-12',
        report_id: 'ai-topic-radar',
        title: 'Legacy Bookmark Target',
        normalized_title: 'legacy bookmark target',
        summary: 'Fixture summary',
        source: 'Fixture Source',
        category: 'Fixture',
        action: '验证',
        score: 100,
        tags: [],
        aliases: [],
        display_fields: {},
      }],
    }),
  }))

  await page.goto(`/#2026-08-12/ai-topic-radar/item/${legacyId}`)
  await expect(page.locator('.item-detail h1')).toHaveText('Legacy Bookmark Target')
  await page.reload()
  await expect(page.locator('.item-detail h1')).toHaveText('Legacy Bookmark Target')

  await page.goto('/#2026-08-10/ai-topic-radar')
  await page.goBack()
  await expect(page.locator('.item-detail h1')).toHaveText('Legacy Bookmark Target')
  await page.goForward()
  await expect(page.locator('.md')).toBeVisible()
})
