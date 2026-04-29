import { FunctionalComponent } from "preact";
import { useEffect, useRef } from "preact/hooks";

interface EquityChartProps {
  strategy_equity: number[];
  baseline_equity: number[];
  timestamps: string[];
}

const EquityChart: FunctionalComponent<EquityChartProps> = ({
  strategy_equity = [],
  baseline_equity = [],
  timestamps = [],
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    if (strategy_equity.length === 0 && baseline_equity.length === 0) {
      containerRef.current.innerHTML = "<p style=\"color:var(--text-secondary)\">No equity data available.</p>";
      return;
    }

    let cancelled = false;

    import("uplot").then((uPlot) => {
      if (cancelled || !containerRef.current) return;

      const len = Math.max(strategy_equity.length, baseline_equity.length);
      const safeTimestamps = timestamps.length > 0 ? timestamps : Array.from({ length: len }, (_, i) => String(i));
      const dates = safeTimestamps.map((t) => new Date(t).getTime() / 1000);

      const data: (number | null)[][] = [dates];
      data.push(strategy_equity.map((v) => (isFinite(v) ? v : null)));
      data.push(baseline_equity.map((v) => (isFinite(v) ? v : null)));

      const opts: any = {
        width: containerRef.current.clientWidth,
        height: 320,
        cursor: { drag: { x: true, y: true } },
        scales: { x: { time: true }, y: { auto: true } },
        axes: [
          { stroke: "var(--text-secondary)", grid: { stroke: "var(--border-color)" } },
          { stroke: "var(--text-secondary)", grid: { stroke: "var(--border-color)" }, size: 60 },
        ],
        series: [
          {},
          {
            label: "Strategy",
            stroke: "var(--healthy)",
            width: 2,
            points: { show: false },
          },
          {
            label: "Buy & Hold",
            stroke: "var(--text-secondary)",
            width: 1,
            dash: [5, 3],
            points: { show: false },
          },
        ],
      };

      try {
        chartRef.current = new uPlot.default(opts, data as any, containerRef.current);
      } catch (err) {
        console.error("uPlot init failed:", err);
        if (containerRef.current) {
          containerRef.current.innerHTML = "<p style=\"color:var(--text-secondary)\">Chart failed to render. See console for details.</p>";
        }
      }
    }).catch((err) => {
      if (!cancelled && containerRef.current) {
        console.error("Failed to load uPlot:", err);
        containerRef.current.innerHTML = "<p style=\"color:var(--text-secondary)\">Chart library unavailable.</p>";
      }
    });

    const handleResize = () => {
      if (chartRef.current && containerRef.current) {
        chartRef.current.setSize({ width: containerRef.current.clientWidth, height: 320 });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      cancelled = true;
      window.removeEventListener("resize", handleResize);
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
    };
  }, [strategy_equity, baseline_equity, timestamps]);

  return <div ref={containerRef} style="width:100%;min-height:320px;" />;
};

export default EquityChart;
