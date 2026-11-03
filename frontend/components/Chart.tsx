"use client";
import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, SVGRenderer]);

/** Categorical order, validated for the light panel surface (#FFFFFF) with the dataviz validator. */
export const SERIES = ["#6A5AE0", "#0E8FA3", "#2F6BEB", "#C2457A"];
const AXIS = { axisLine: { lineStyle: { color: "rgba(40,52,110,0.18)" } }, axisTick: { show: false },
  axisLabel: { color: "#596282", fontFamily: "IBM Plex Sans", fontSize: 11 }, splitLine: { lineStyle: { color: "rgba(40,52,110,0.07)" } } };

type Series = { name: string; data: number[] };

export function Chart({ kind, categories, series, height = 220, horizontal, stack, label }: {
  kind: "bar" | "line"; categories: string[]; series: Series[]; height?: number; horizontal?: boolean; stack?: boolean; label?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const c = echarts.init(ref.current, undefined, { renderer: "svg" });
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const cat = { type: "category" as const, data: categories, ...AXIS, splitLine: { show: false } };
    const val = { type: "value" as const, ...AXIS, minInterval: 1 };
    c.setOption({
      animation: !reduce,
      color: SERIES,
      grid: { left: horizontal ? 8 : 4, right: 12, top: series.length > 1 ? 34 : 12, bottom: 4, containLabel: true },
      legend: series.length > 1 ? { top: 0, left: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, textStyle: { color: "#3C4466", fontSize: 12 } } : undefined,
      tooltip: { trigger: "axis", axisPointer: { type: kind === "line" ? "line" : "shadow", lineStyle: { color: "rgba(14,143,163,0.45)" }, shadowStyle: { color: "rgba(40,52,110,0.05)" } },
        backgroundColor: "rgba(255,255,255,0.98)", borderColor: "rgba(40,52,110,0.18)", textStyle: { color: "#141A33", fontSize: 12 } },
      xAxis: horizontal ? val : cat,
      yAxis: horizontal ? cat : val,
      series: series.map((s) => kind === "bar"
        ? { type: "bar", name: s.name, data: s.data, stack: stack ? "s" : undefined, barMaxWidth: 22,
            itemStyle: { borderRadius: stack ? 0 : horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0], borderColor: "#FFFFFF", borderWidth: stack ? 2 : 0 } }
        : { type: "line", name: s.name, data: s.data, smooth: 0.25, symbol: "circle", symbolSize: 8, showSymbol: s.data.length < 20, lineStyle: { width: 2 },
            itemStyle: { borderColor: "#FFFFFF", borderWidth: 2 } }),
    });
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(ref.current);
    return () => { ro.disconnect(); c.dispose(); };
  }, [kind, categories, series, horizontal, stack]);
  const table = (
    <table className="sr-only">
      <caption>{label}</caption>
      <thead><tr><th>Category</th>{series.map((s) => <th key={s.name}>{s.name}</th>)}</tr></thead>
      <tbody>{categories.map((c, i) => <tr key={c}><td>{c}</td>{series.map((s) => <td key={s.name}>{s.data[i]}</td>)}</tr>)}</tbody>
    </table>
  );
  return <div><div ref={ref} style={{ height }} role="img" aria-label={label} />{table}</div>;
}
