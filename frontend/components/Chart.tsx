"use client";
import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";
import { cssVar, tokenColor, useTheme } from "@/components/theme";

echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, SVGRenderer]);

/** Categorical palettes are theme tokens (--chart-1..4), each validated with the dataviz validator for its
 * own surface: light #FBF9F4 (bronze, blue, green, violet) and dark #0E1426 (the original order). */
const chartPalette = () => [1, 2, 3, 4].map((i) => cssVar(`--chart-${i}`));
const axis = () => ({ axisLine: { lineStyle: { color: tokenColor("line", 0.35) } }, axisTick: { show: false },
  axisLabel: { color: tokenColor("ink-mute"), fontFamily: "IBM Plex Mono", fontSize: 10.5 }, splitLine: { lineStyle: { color: tokenColor("line", 0.18), type: "dashed" as const } } });

type Series = { name: string; data: number[] };

export function Chart({ kind, categories, series, height = 220, horizontal, stack, label }: {
  kind: "bar" | "line"; categories: string[]; series: Series[]; height?: number; horizontal?: boolean; stack?: boolean; label?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const theme = useTheme();
  useEffect(() => {
    const AXIS = axis(), SERIES = chartPalette(), surface = tokenColor("surface");
    if (!ref.current) return;
    const c = echarts.init(ref.current, undefined, { renderer: "svg" });
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const cat = { type: "category" as const, data: categories, ...AXIS, splitLine: { show: false } };
    const val = { type: "value" as const, ...AXIS, minInterval: 1 };
    c.setOption({
      animation: !reduce,
      color: SERIES,
      grid: { left: horizontal ? 8 : 4, right: 12, top: series.length > 1 ? 34 : 12, bottom: 4, containLabel: true },
      legend: series.length > 1 ? { top: 0, left: 0, icon: "rect", itemWidth: 10, itemHeight: 10, textStyle: { color: tokenColor("ink-soft"), fontSize: 12, fontFamily: "Manrope Variable" } } : undefined,
      tooltip: { trigger: "axis", axisPointer: { type: kind === "line" ? "line" : "shadow", lineStyle: { color: tokenColor("ink", 0.35) }, shadowStyle: { color: tokenColor("ink", 0.04) } },
        backgroundColor: surface, borderColor: tokenColor("line", 1), borderRadius: 2, textStyle: { color: tokenColor("ink"), fontSize: 12 } },
      xAxis: horizontal ? val : cat,
      yAxis: horizontal ? cat : val,
      series: series.map((s) => kind === "bar"
        ? { type: "bar", name: s.name, data: s.data, stack: stack ? "s" : undefined, barMaxWidth: 22,
            itemStyle: { borderRadius: 0, borderColor: surface, borderWidth: stack ? 2 : 0 } }
        : { type: "line", name: s.name, data: s.data, smooth: 0.25, symbol: "circle", symbolSize: 8, showSymbol: s.data.length < 20, lineStyle: { width: 2 },
            itemStyle: { borderColor: surface, borderWidth: 2 } }),
    });
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(ref.current);
    return () => { ro.disconnect(); c.dispose(); };
  }, [kind, categories, series, horizontal, stack, theme]);
  const table = (
    <table className="sr-only">
      <caption>{label}</caption>
      <thead><tr><th>Category</th>{series.map((s) => <th key={s.name}>{s.name}</th>)}</tr></thead>
      <tbody>{categories.map((c, i) => <tr key={c}><td>{c}</td>{series.map((s) => <td key={s.name}>{s.data[i]}</td>)}</tr>)}</tbody>
    </table>
  );
  return <div><div ref={ref} style={{ height }} role="img" aria-label={label} />{table}</div>;
}
