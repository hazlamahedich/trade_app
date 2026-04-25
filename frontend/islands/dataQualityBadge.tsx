import { h, FunctionComponent } from "preact";
import { useState } from "preact/hooks";

interface DataQualityBadgeProps {
  level: "PASS" | "WARN" | "FAIL";
  anomalyCount?: number;
}

const badgeColors: Record<string, string> = {
  PASS: "bg-green-100 text-green-800",
  WARN: "bg-yellow-100 text-yellow-800",
  FAIL: "bg-red-100 text-red-800",
};

const DataQualityBadge: FunctionComponent<DataQualityBadgeProps> = ({
  level,
  anomalyCount = 0,
}) => {
  const [expanded, setExpanded] = useState(false);

  return h(
    "span",
    {
      class: `inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${badgeColors[level] || "bg-gray-100 text-gray-800"}`,
      onClick: () => setExpanded(!expanded),
      style: { cursor: "pointer" },
    },
    h("span", null, level === "PASS" ? "✓" : level === "FAIL" ? "✗" : "⚠"),
    h("span", null, `Data: ${level}`),
    expanded && anomalyCount > 0
      ? h("span", { class: "ml-1" }, `(${anomalyCount} anomalies)`)
      : null
  );
};

export default DataQualityBadge;
