# Golden Questions

These questions are the first evaluation set for AI Trend Radar RAG. A golden question is not a perfect answer. It is a specification for what the system must retrieve, cite, and avoid hallucinating.

The machine-readable evaluation asset is `docs/rag-transformation/evals/golden-questions.json`.

Use this Markdown file for human review and discussion. Use the JSON file for validation, future benchmark runs, and CI-friendly checks.

## How To Read The Fields

- **Question:** The user-facing question.
- **Primary intent:** What job the user is trying to do.
- **Expected retrieval:** What sources the system should try first.
- **Good answer:** What a satisfactory answer must include.
- **Bad answer:** What failure looks like.
- **Web search policy:** Whether future web search is allowed when internal corpus is insufficient.

## Q1: Recent RAG Developments

**Question:** 最近 RAG 领域有什么值得关注的新动向？

**Primary intent:** Recent trend discovery.

**Expected retrieval:** Recent AI Trend Radar corpus, especially topics and reports containing RAG, retrieval, vector database, knowledge graph, agentic RAG, or evaluation.

**Good answer:** Lists several recent movements, cites dates and sources, separates strong corpus-backed claims from weaker observations, and explains why each item matters.

**Bad answer:** Gives generic RAG textbook knowledge without citing recent AI Trend Radar evidence.

**Web search policy:** Allowed later if internal corpus has too little recent RAG evidence; external findings must be labeled as external.

## Q2: RAG Evolution Route

**Question:** 请帮我梳理一下 RAG 技术的发展演进路线，以及相关的论文、文章等资料。

**Primary intent:** Background research and learning map.

**Expected retrieval:** Internal corpus first, then future external search for papers/articles because this question likely exceeds the daily corpus.

**Good answer:** Explains the evolution from basic retrieve-then-read systems to hybrid search, reranking, Graph RAG, Agentic RAG, evaluation, and production governance. It clearly says which parts are supported by internal corpus and which parts need external references.

**Bad answer:** Pretends the internal corpus contains a complete academic history when it does not.

**Web search policy:** Allowed later and likely necessary.

## Q3: Recent Claude Updates

**Question:** Claude 最近有没有上线什么新功能？比如新的插件或者类似的功能更新。

**Primary intent:** Company/product update tracking.

**Expected retrieval:** Recent AI Trend Radar corpus with source values such as Anthropic, Claude, Product Hunt, GitHub, and related topic tags.

**Good answer:** Distinguishes product features, developer tools, ecosystem updates, research updates, and partnerships. Each key claim has date and source.

**Bad answer:** Says "Claude has many updates" without dates, sources, or distinction between feature/research/partnership.

**Web search policy:** Allowed later for latest official Anthropic confirmation.

## Q4: GitHub Hot Topics Last Week

**Question:** 过去一周 GitHub 热榜上有什么值得关注的选题？

**Primary intent:** Weekly source-specific topic discovery.

**Expected retrieval:** Last seven days of AI Trend Radar corpus, especially topics with source values containing GitHub Trending or GitHub Search.

**Good answer:** Lists notable projects/topics, explains why they are worth watching, includes score or heat signal when available, and cites date/source.

**Bad answer:** Mixes Product Hunt, OpenAI, Anthropic, and GitHub items without saying which are GitHub-sourced.

**Web search policy:** Not needed for P0 if the internal corpus has GitHub source data.

## Q5: Google OKF And ALM Wiki

**Question:** 比如最近 Google 出了一个 OKF，它与之前提出的 ALM Wiki 知识框架有什么关系？既然是 Google 提出来的，它整体的核心思想是什么？在提升用户偏好效率方面表现如何？

**Primary intent:** Deep technical comparison.

**Expected retrieval:** Internal corpus for Google/DeepMind/OKF/ALM Wiki references. If internal corpus lacks evidence, answer must say evidence is insufficient.

**Good answer:** First reports whether internal corpus contains OKF and ALM Wiki evidence. If not enough evidence exists, it refuses to invent the relationship and recommends external research.

**Bad answer:** Fabricates a relationship or performance claim without citations.

**Web search policy:** Allowed later and likely necessary.

## Q6: AI Agent Cross-Date Signals

**Question:** AI Agent 相关主题最近是否跨多个日期和来源持续出现？这些信号说明了什么？

**Primary intent:** Graph relationship trend coverage for AI Agent topics.

**Expected retrieval:** Neo4j graph plus recent AI Trend Radar corpus containing AI Agent, agentic, 智能体, workflow, or tool-use signals.

**Good answer:** Uses graph relationship evidence when available, reports whether Agent-related topics recur across dates and sources, and avoids claiming market certainty from counts alone.

**Bad answer:** Gives a generic Agent definition, claims a long-term trend without dated evidence, or treats graph counts as proof of business adoption.

**Web search policy:** Not needed for first-pass internal graph coverage; external search may be used later for adoption claims.

## Q7: AI Coding And Developer Tools

**Question:** 最近有哪些 AI 编码工具或开发者工具值得关注？它们分别解决什么问题？

**Primary intent:** Developer-tool trend discovery.

**Expected retrieval:** Recent AI Trend Radar topic-pool candidates and reports containing developer tools, coding, Claude Code, Artifacts, GitHub, or AI coding signals.

**Good answer:** Groups tools by user problem such as coding workflow, sharing, debugging, or automation; includes dates and sources; separates product launches from open-source repository signals.

**Bad answer:** Lists tool names without explaining use cases, mixes coding tools with unrelated AI products, or claims official capabilities without evidence.

**Web search policy:** Optional for official confirmation; internal corpus is enough for trend discovery.

## Q8: Product Hunt AI Products

**Question:** 最近 Product Hunt 上有哪些 AI 产品值得深挖？为什么？

**Primary intent:** Source-specific Product Hunt product discovery.

**Expected retrieval:** AI Trend Radar topic-pool candidates sourced from Product Hunt.

**Good answer:** Only treats Product Hunt-sourced items as Product Hunt evidence, explains why each product is worth deep research, and includes score or heat signal when available.

**Bad answer:** Mixes GitHub and Product Hunt items without labeling, recommends products without source/date, or turns launch buzz into unsupported business traction claims.

**Web search policy:** Not needed for first-pass Product Hunt source review.

## Q9: OpenAI Trend Signals

**Question:** OpenAI 最近相关的趋势信号主要集中在哪些方向？这些信号来自哪些来源？

**Primary intent:** Company-centered trend synthesis.

**Expected retrieval:** Neo4j graph and recent AI Trend Radar corpus containing OpenAI, GPT, agent, developer, or model signals.

**Good answer:** Summarizes themes rather than a raw list, reports source/date coverage, and avoids official-company claims unless official evidence exists.

**Bad answer:** Uses model memory about OpenAI instead of local evidence, claims official releases without source quality, or ignores graph relationship coverage when available.

**Web search policy:** Allowed later only for official OpenAI confirmation; internal trend synthesis should stay labeled as internal.

## Q10: Repeated Cross-Source Themes

**Question:** 哪些 AI 主题在最近语料中跨多个来源反复出现？请按主题归类。

**Primary intent:** Cross-source repeated topic discovery.

**Expected retrieval:** Neo4j graph plus recent topic-pool candidates with topic/source/date relationships.

**Good answer:** Groups repeated themes, shows which dates and sources support each theme, and separates strong repeated signals from one-off items.

**Bad answer:** Reports one-off items as repeated trends, omits dates or sources, or uses external web popularity as if it came from internal corpus.

**Web search policy:** Not needed for internal repeated-signal analysis.

## Q11: Commercial Success Evidence Sufficiency

**Question:** 当前语料中有没有足够证据说明某个 AI 产品已经取得明确商业成功？

**Primary intent:** Evidence sufficiency and refusal behavior.

**Expected retrieval:** AI Trend Radar corpus and source review for commercial success, revenue, customers, traction, or 商业成功 signals.

**Good answer:** Explains what evidence would be required to claim commercial success, refuses to infer business success from launch buzz alone, and suggests follow-up evidence to collect.

**Bad answer:** Treats Product Hunt heat or GitHub stars as commercial success, claims revenue or customer adoption without citations, or fails to state evidence insufficiency.

**Web search policy:** Allowed later if official or reliable business evidence is needed; otherwise answer should remain insufficient.

## Q12: Source Signal Comparison

**Question:** 请比较 Claude Code Artifacts、GitHub 热榜 AI 项目和 Product Hunt AI 产品三类信号的差异。

**Primary intent:** Source-comparison and signal-quality analysis.

**Expected retrieval:** AI Trend Radar corpus across Product Hunt and GitHub sources, plus Claude Code Artifacts evidence.

**Good answer:** Compares product launch, developer activity, and source-specific trend signal; explains what each source can and cannot prove; avoids ranking signals without evidence criteria.

**Bad answer:** Treats all sources as equally reliable for the same claim, confuses product launch signal with open-source adoption, or does not cite one example from each signal type.

**Web search policy:** Not needed for first-pass internal source comparison; external search may be used later for official confirmation.
