"use client";
import dynamic from "next/dynamic";
import { Skeleton } from "@/components/ui/primitives";

/**
 * Monaco served from this app (/monaco/vs, copied from node_modules at build time) instead of the public CDN
 * that @monaco-editor/react uses by default. Corporate and offline networks often block that CDN, and then the
 * policy and workflow editors would silently never appear.
 */
export const CodeEditor = dynamic(async () => {
  const m = await import("@monaco-editor/react");
  m.loader.config({ paths: { vs: "/monaco/vs" } });
  return m.default;
}, { ssr: false, loading: () => <Skeleton className="h-72" /> });
