export interface TAEventMapType {
  "ta:data:fetched": { symbol: string; interval: string; rows: number };
  "ta:data:validated": {
    symbol: string;
    level: "PASS" | "WARN" | "FAIL";
    anomalyCount: number;
  };
  "ta:strategy:forked": { strategyId: string; parentRunId?: string };
  "ta:strategy:run_started": { runId: string; strategyId: string };
  "ta:strategy:run_completed": {
    runId: string;
    totalReturn: number;
    sharpe: number;
  };
  "ta:backtest:progress": { runId: string; current: number; total: number };
  "ta:backtest:completed": { runId: string; metrics: Record<string, number> };
  "ta:experiment:created": { runId: string; configHash: string };
}

export type TADomain = "data" | "strategy" | "backtest" | "experiment";

export function buildEventType(
  domain: TADomain,
  action: string
): `ta:${TADomain}:${string}` {
  return `ta:${domain}:${action}`;
}
