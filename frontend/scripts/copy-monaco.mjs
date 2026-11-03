// Copies the Monaco AMD build into public/ so the editor never depends on a CDN.
import { cpSync, existsSync, rmSync } from "node:fs";
const src = "node_modules/monaco-editor/min/vs", dst = "public/monaco/vs";
if (!existsSync(src)) { console.error(`missing ${src}; run npm install`); process.exit(1); }
rmSync(dst, { recursive: true, force: true });
cpSync(src, dst, { recursive: true });
console.log(`copied ${src} -> ${dst}`);
