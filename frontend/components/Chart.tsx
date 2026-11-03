"use client";
import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, SVGRenderer]);

/** Categorical order, validated for the dark surface (#0E1426) with the dataviz validator. */
export const SERIES = ["#8B7CFF", "#1FA3B5", "#3D7BFF", "#D26A92"];
const AXIS = { axisLine: { lineStyle: { color: "rgba(139,148,255,0.18)" } }, axisTick: { show: false },
  axisLabel: { color: "#7A83A6", fontFamily: "IBM Plex Sans", fontSize: 11 }, splitLine: { lineStyle: { color: "rgba(139,148,255,0.07)" } } };

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
      legend: series.length > 1 ? { top: 0, left: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, textStyle: { color: "#B8BFDB", fontSize: 12 } } : undefined,
      tooltip: { trigger: "axis", axisPointer: { type: kind === "line" ? "line" : "shadow", lineStyle: { color: "rgba(56,225,240,0.4)" }, shadowStyle: { color: "rgba(139,148,255,0.06)" } },
        backgroundColor: "rgba(19,27,51,0.96)", borderColor: "rgba(139,148,255,0.25)", textStyle: { color: "#EEF1FF", fontSize: 12 } },
      xAxis: horizontal ? val : cat,
      yAxis: horizontal ? cat : val,
      series: series.map((s) => kind === "bar"
        ? { type: "bar", name: s.name, data: s.data, stack: stack ? "s" : undefined, barMaxWidth: 22,
            itemStyle: { borderRadius: stack ? 0 : horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0], borderColor: "#0E1426", borderWidth: stack ? 2 : 0 } }
        : { type: "line", name: s.name, data: s.data, smooth: 0.25, symbol: "circle", symbolSize: 8, showSymbol: s.data.length < 20, lineStyle: { width: 2 },
            itemStyle: { borderColor: "#0E1426", borderWidth: 2 } }),
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
