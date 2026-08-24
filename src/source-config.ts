export type SourceId =
  | "anthropic"
  | "openai"
  | "deepmind"
  | "github_trending"
  | "hacker_news"
  | "product_hunt"
  | "arxiv"
  | "hugging_face"
  | "devto"
  | "lobsters"
  | "kr36"
  | "infoq_cn"
  | "gitee"
  | "oschina"
  | "juejin";
export type SourceMode = "auto" | "enabled" | "disabled";
export type SourceModes = Partial<Record<SourceId, SourceMode>>;
export type SourceStatus = "ready" | "skipped" | "error" | "disabled";

interface SourceDefinition {
  id: SourceId;
  name: string;
  credentialEnv?: string;
}

export interface ResolvedSourceState extends SourceDefinition {
  mode: SourceMode;
  active: boolean;
  status: SourceStatus;
  message: string;
  missingCredential?: string;
}

export type ResolvedSourceConfiguration = Record<SourceId, ResolvedSourceState>;

export interface SourceConfigurationSummary {
  ok: boolean;
  lines: string[];
}

export const SOURCE_CATALOG: Record<SourceId, SourceDefinition> = {
  anthropic: { id: "anthropic", name: "Anthropic" },
  openai: { id: "openai", name: "OpenAI" },
  deepmind: { id: "deepmind", name: "Google DeepMind" },
  github_trending: { id: "github_trending", name: "GitHub Trending" },
  hacker_news: { id: "hacker_news", name: "Hacker News" },
  product_hunt: {
    id: "product_hunt",
    name: "Product Hunt",
    credentialEnv: "PRODUCTHUNT_TOKEN",
  },
  arxiv: { id: "arxiv", name: "arXiv" },
  hugging_face: { id: "hugging_face", name: "Hugging Face" },
  devto: { id: "devto", name: "DEV Community" },
  lobsters: { id: "lobsters", name: "Lobsters" },
  kr36: { id: "kr36", name: "36Kr" },
  infoq_cn: { id: "infoq_cn", name: "InfoQ 中国" },
  gitee: { id: "gitee", name: "Gitee" },
  oschina: { id: "oschina", name: "开源中国" },
  juejin: { id: "juejin", name: "掘金" },
};

export function resolveSourceConfiguration(
  modes: SourceModes = {},
  env: Record<string, string | undefined> = process.env,
): ResolvedSourceConfiguration {
  return Object.fromEntries(
    Object.values(SOURCE_CATALOG).map((definition) => {
      const mode = modes[definition.id] ?? "auto";
      const hasCredential = !definition.credentialEnv || Boolean(env[definition.credentialEnv]?.trim());
      let state: ResolvedSourceState;

      if (mode === "disabled") {
        state = { ...definition, mode, active: false, status: "disabled", message: "已关闭" };
      } else if (hasCredential) {
        state = { ...definition, mode, active: true, status: "ready", message: "可运行" };
      } else if (mode === "enabled") {
        state = {
          ...definition,
          mode,
          active: false,
          status: "error",
          message: `缺少 ${definition.credentialEnv}`,
          missingCredential: definition.credentialEnv,
        };
      } else {
        state = {
          ...definition,
          mode,
          active: false,
          status: "skipped",
          message: `未配置 ${definition.credentialEnv}，本次跳过`,
          missingCredential: definition.credentialEnv,
        };
      }

      return [definition.id, state];
    }),
  ) as ResolvedSourceConfiguration;
}

export function assertSourceConfigurationReady(states: ResolvedSourceConfiguration): void {
  const errors = Object.values(states).filter((state) => state.status === "error");
  if (errors.length) {
    throw new Error(errors.map((state) => `${state.name}: ${state.message}`).join("; "));
  }
}

export function summarizeSourceConfiguration(
  states: ResolvedSourceConfiguration,
): SourceConfigurationSummary {
  const values = Object.values(states);
  return {
    ok: values.every((state) => state.status !== "error"),
    lines: values.map((state) => `${state.name}: ${state.status} — ${state.message}`),
  };
}

export async function runConfiguredSource<T>(
  state: ResolvedSourceState,
  connector: () => Promise<T>,
  inactiveResult: T,
): Promise<T> {
  if (!state.active) {
    console.log(`  [source/${state.id}] ${state.message}`);
    return inactiveResult;
  }
  return connector();
}
