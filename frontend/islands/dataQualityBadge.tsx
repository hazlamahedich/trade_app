import { h, FunctionComponent } from "preact";
import { useState } from "preact/hooks";

interface DataQualityBadgeProps {
  level: "PASS" | "WARN" | "FAIL";
  anomalyCount?: number;
}

const colorMap: Record<string, { bg: string; text: string }> = {
  PASS: { bg: "var(--healthy)", text: "#fff" },
  WARN: { bg: "var(--caution)", text: "#fff" },
  FAIL: { bg: "var(--degraded)", text: "#fff" },
};

const iconMap: Record<string, string> = {
  PASS: "✓",
  FAIL: "✗",
  WARN: "⚠",
};

const DataQualityBadge: FunctionComponent<DataQualityBadgeProps> = ({
  level,
  anomalyCount = 0,
}) => {
  const [expanded, setExpanded] = useState(false);

  const colors = colorMap[level] || { bg: "var(--border-color)", text: "var(--text-primary)" };
  const icon = iconMap[level] || "⚠";

  return h(
    "span",
    {
      style: {
        display: "inline-flex",
        alignItems: "center",
        gap: "0.25rem",
        padding: "2px 8px",
        borderRadius: "4px",
        fontSize: "0.75rem",
        fontWeight: 600,
        background: colors.bg,
        color: colors.text,
        cursor: "pointer",
      },
      onClick: () => setExpanded(!expanded),
    },
    h("span", null, icon),
    h("span", null, `Data: ${level}`),
    expanded && anomalyCount > 0
      ? h("span", { style: { marginLeft: "0.25rem" } }, `(${anomalyCount} anomalies)`)
      : null
  );
};

export default DataQualityBadge;
