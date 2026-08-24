import "dotenv/config";

import { loadConfig } from "./config.ts";
import { resolveSourceConfiguration, summarizeSourceConfiguration } from "./source-config.ts";

const config = loadConfig();
const summary = summarizeSourceConfiguration(resolveSourceConfiguration(config.sourceModes));

console.log("Data source preflight");
for (const line of summary.lines) console.log(`- ${line}`);

if (!summary.ok) process.exitCode = 1;
