import { h } from "preact";
import { useEffect, useState, useRef } from "preact/hooks";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";

export default function WalkForwardChart({ runId }: { runId: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<any>(null);
  const [auditMode, setAuditMode] = useState(false);
  const plotRef = useRef<uPlot | null>(null);

  useEffect(() => {
    const handler = (e: any) => setAuditMode(e.detail.enabled);
    window.addEventListener("ta:audit-mode", handler);
    return () => window.removeEventListener("ta:audit-mode", handler);
  }, []);

  useEffect(() => {
    let interval: any;
    const fetchResults = () => {
      fetch(`/api/walkforward/${runId}`)
        .then(res => {
          if (!res.ok) return null;
          return res.json();
        })
        .then(json => {
          if (json) {
            setData(json);
            if (interval) clearInterval(interval);
          }
        })
        .catch(err => console.error(err));
    };
    
    fetchResults();
    interval = setInterval(fetchResults, 2000);
    return () => clearInterval(interval);
  }, [runId]);

  useEffect(() => {
    if (!data || !containerRef.current) return;
    
    const times = data.equity.map((d: any) => new Date(d.time).getTime() / 1000);
    const eqVals = data.equity.map((d: any) => d.value);
    
    const plotData: any[] = [times, eqVals];
    const series: any[] = [
      {},
      {
        label: "Strategy (OOS)",
        stroke: data.wfe < 0.5 ? "var(--degraded-muted, #999)" : "var(--healthy, green)",
        width: 2,
      }
    ];

    if (data.baseline && data.baseline.length > 0) {
      const baselineMap = new Map(data.baseline.map((d: any) => [new Date(d.time).getTime() / 1000, d.value]));
      const baseVals = times.map((t: number) => baselineMap.get(t) || null);
      plotData.push(baseVals);
      series.push({
        label: "Baseline",
        stroke: "var(--text-secondary, gray)",
        width: 1,
        dash: [5, 5]
      });
    }

    const opts: uPlot.Options = {
      width: containerRef.current.clientWidth || 800,
      height: 400,
      series: series,
      hooks: {
        draw: [
          (u) => {
            if (!auditMode) return;
            // Draw OOS "Scars" - vertical lines at window boundaries
            const { ctx } = u;
            ctx.save();
            ctx.strokeStyle = "rgba(255, 0, 0, 0.3)";
            ctx.setLineDash([2, 4]);
            ctx.lineWidth = 1;
            
            data.windows.forEach((w: any) => {
               const val = new Date(w.oos_start).getTime() / 1000;
               const x = u.valToPos(val, "x", true);
               ctx.beginPath();
               ctx.moveTo(x, u.bbox.top);
               ctx.lineTo(x, u.bbox.top + u.bbox.height);
               ctx.stroke();
            });
            ctx.restore();
          }
        ]
      },
      axes: [
        {},
        {
          values: (u, vals) => vals.map(v => "$" + v.toFixed(0))
        }
      ]
    };

    if (plotRef.current) {
      plotRef.current.destroy();
    }
    plotRef.current = new uPlot(opts, plotData as uPlot.AlignedData, containerRef.current);

    return () => {
      if (plotRef.current) {
        plotRef.current.destroy();
        plotRef.current = null;
      }
    };
  }, [data, auditMode]);

  if (!data) return <div>Waiting for run to complete...</div>;

  return (
    <div class={data.wfe < 0.5 ? "pressed-flower" : ""}>
      <div style={{ display: "flex", gap: "10px", marginBottom: "10px", alignItems: "center", flexWrap: "wrap" }}>
          <span class="badge" style={{ backgroundColor: data.wfe_status === 'healthy' ? 'var(--healthy)' : data.wfe_status === 'caution' ? 'var(--caution)' : 'var(--degraded)', color: 'white' }}>
            WFE: {data.wfe.toFixed(2)} ({data.wfe_status.toUpperCase()})
          </span>
          {data.diagnostics && data.diagnostics.dsr !== null && (
              <span class="badge" style={{ backgroundColor: data.diagnostics.dsr_significant ? "var(--healthy)" : "var(--degraded)", color: "white" }}>
                  DSR: {(data.diagnostics.dsr * 100).toFixed(1)}% {data.diagnostics.dsr_significant ? "Sig." : "NOT Sig."}
              </span>
          )}
          {data.regime_variance > 0.1 && (
              <span class="badge badge-caution">Regime Var: {(data.regime_variance * 100).toFixed(0)}%</span>
          )}
          {data.diagnostics && data.diagnostics.dsr_warning && (
              <span style={{ fontSize: "0.85rem", color: "var(--degraded)" }}>⚠ {data.diagnostics.dsr_warning}</span>
          )}
      </div>
      <div ref={containerRef} style={{ width: "100%", height: "400px" }}></div>
      {auditMode && data.diagnostics?.hints && (
          <div class="card" style={{ marginTop: "1rem", borderLeft: "4px solid var(--caution)" }}>
              <h4 style={{ margin: 0 }}>Quant Audit Hints</h4>
              <ul style={{ fontSize: "0.85rem", paddingLeft: "1.2rem" }}>
                  {Object.entries(data.diagnostics.hints).map(([k, v]: [string, any]) => (
                      <li key={k}>{v}</li>
                  ))}
              </ul>
          </div>
      )}
    </div>
  );
}
