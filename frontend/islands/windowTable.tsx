import { h } from "preact";
import { useEffect, useState } from "preact/hooks";

export default function WindowTable({ runId }: { runId: string }) {
  const [data, setData] = useState<any>(null);
  const [auditMode, setAuditMode] = useState(false);

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
          if (res.ok) return res.json();
          return null;
        })
        .then(json => {
          if (json) {
            setData(json);
            if (interval) clearInterval(interval);
          }
        });
    };
    
    fetchResults();
    interval = setInterval(fetchResults, 2000);
    return () => clearInterval(interval);
  }, [runId]);

  if (!data) return null;

  const getHeatmapColor = (val: number, min: number, max: number) => {
      const ratio = (val - min) / (max - min || 1);
      if (ratio > 0.5) return `rgba(34, 197, 94, ${ratio})`; // Healthy green
      return `rgba(239, 68, 68, ${1 - ratio})`; // Degraded red
  };

  const isSharpes = data.windows.map((w: any) => w.is_sharpe);
  const minIs = Math.min(...isSharpes);
  const maxIs = Math.max(...isSharpes);

  return (
    <div style={{ overflowX: "auto" }}>
      <table class="heatmap-table">
        <thead>
          <tr>
            <th>Window</th>
            <th>IS Sharpe</th>
            <th>OOS Sharpe</th>
            {auditMode && <th>IS Return</th>}
            {auditMode && <th>OOS Return</th>}
            <th>Params {auditMode && "(Drift Heatmap)"}</th>
          </tr>
        </thead>
        <tbody>
          {data.windows.map((w: any, idx: number) => {
            const prevParams = idx > 0 ? data.windows[idx-1].params : null;
            const driftKeys = prevParams ? Object.keys(w.params || {}).filter(k => w.params[k] !== prevParams[k]) : [];
            const hasDrift = driftKeys.length > 0;

            return (
              <tr key={w.window_idx}>
                <td>{w.window_idx}</td>
                <td class="tabular-nums" style={{ backgroundColor: getHeatmapColor(w.is_sharpe, minIs, maxIs), color: 'white' }}>
                    {(w.is_sharpe || 0).toFixed(2)}
                </td>
                <td class="tabular-nums" style={{ borderLeft: "2px solid var(--border-color)", fontWeight: "bold", color: w.oos_sharpe >= 0 ? "var(--healthy)" : "var(--degraded)" }}>
                  {(w.oos_sharpe || 0).toFixed(2)}
                </td>
                {auditMode && <td class="tabular-nums">{(w.is_return * 100 || 0).toFixed(1)}%</td>}
                {auditMode && <td class="tabular-nums">{(w.oos_return * 100 || 0).toFixed(1)}%</td>}
                <td class="data-font" style={{ fontSize: "0.8rem", position: "relative" }}>
                  <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                      {w.params && Object.entries(w.params).map(([k, v]: [string, any]) => (
                          <span key={k} style={{ 
                              padding: "2px 4px", 
                              borderRadius: "2px", 
                              backgroundColor: driftKeys.includes(k) ? "var(--caution)" : "var(--bg-secondary)",
                              color: driftKeys.includes(k) ? "white" : "inherit",
                              border: driftKeys.includes(k) ? "none" : "1px solid var(--border-color)"
                          }}>
                              {k}:{v}
                          </span>
                      ))}
                  </div>
                  {auditMode && hasDrift && <div style={{ fontSize: "0.6rem", color: "var(--caution)", marginTop: "2px" }}>DRIFT DETECTED: {driftKeys.join(', ')}</div>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
