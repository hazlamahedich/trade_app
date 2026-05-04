import { registerIsland, initBridge } from "./islands/bridgeUtils";
import DataQualityBadge from "./islands/dataQualityBadge";
import EquityChart from "./islands/equityChart";
import WalkForwardChart from "./islands/walkForwardChart";
import WindowTable from "./islands/windowTable";

registerIsland("dataQualityBadge", DataQualityBadge, { level: "PASS" });
registerIsland("equityChart", EquityChart);
registerIsland("walkForwardChart", WalkForwardChart);
registerIsland("windowTable", WindowTable);

export const teardownBridge = initBridge();