import { registerIsland, initBridge } from "./islands/bridgeUtils";
import DataQualityBadge from "./islands/dataQualityBadge";

registerIsland("dataQualityBadge", DataQualityBadge, { level: "PASS" });

export const teardownBridge = initBridge();
