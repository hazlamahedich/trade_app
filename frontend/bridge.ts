import { registerIsland, initBridge } from "./islands/bridgeUtils";
import DataQualityBadge from "./islands/dataQualityBadge";
import EquityChart from "./islands/equityChart";

registerIsland("dataQualityBadge", DataQualityBadge, { level: "PASS" });
registerIsland("equityChart", EquityChart);

export const teardownBridge = initBridge();
