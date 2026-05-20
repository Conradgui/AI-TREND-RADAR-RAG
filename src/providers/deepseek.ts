import { OpenAICompatibleProvider } from "./openai-compatible.ts";

export class DeepSeekProvider extends OpenAICompatibleProvider {
  readonly name = "deepseek";

  constructor(apiKey = process.env["DEEPSEEK_API_KEY"], model = process.env["DEEPSEEK_MODEL"]) {
    if (!apiKey) {
      throw new Error(
        "Missing DEEPSEEK_API_KEY. Set it with: export LLM_PROVIDER=deepseek; " +
          'printf "DeepSeek API key: "; read -r -s DEEPSEEK_API_KEY; printf "\\n"; export DEEPSEEK_API_KEY',
      );
    }

    super({
      apiKey,
      baseURL: "https://api.deepseek.com",
      model: model ?? "deepseek-chat",
    });
  }
}
