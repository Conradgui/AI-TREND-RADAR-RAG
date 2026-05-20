# AI Topic Radar

AI Topic Radar is a public-source AI topic monitoring workflow for Chinese content operations and product research. It collects daily signals from GitHub, Hacker News, Product Hunt, arXiv, Hugging Face, official AI company updates, and developer communities, then generates a decision-first topic pool.

The default output is Chinese:

- `digests/YYYY-MM-DD/ai-topic-radar.html`: standalone report, directly openable and shareable.
- `digests/YYYY-MM-DD/ai-topic-radar.md`: Markdown copy of the main report.
- `digests/YYYY-MM-DD/topic-pool.json`: structured topic pool.
- `manifest.json` and `feed.xml`: Web UI and RSS distribution.

This project is adapted from [`duanyytop/agents-radar`](https://github.com/duanyytop/agents-radar). It keeps the TypeScript fetch pipeline, GitHub Actions automation, notifications, RSS, and Web UI, while adding Chinese editorial topic scoring, category mapping, action thresholds, and a standalone HTML report.

For complete setup, configuration, and usage instructions, see [README.zh.md](README.zh.md).

Quick start:

```bash
pnpm install --frozen-lockfile

export LLM_PROVIDER=deepseek
printf "DeepSeek API key: "
read -r -s DEEPSEEK_API_KEY
printf "\n"
export DEEPSEEK_API_KEY

pnpm digest
```

Security note: never commit real API keys, tokens, `.env` values, or private reports.
