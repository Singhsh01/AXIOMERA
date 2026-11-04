/** @type {import('next').NextConfig} */
// AXIOMERA_API_URL; the pre-rename ORKESTR_API_URL is still honoured.
const api = process.env.AXIOMERA_API_URL || process.env.ORKESTR_API_URL || "http://localhost:8000";
export default {
  output: "standalone",
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${api}/api/:path*` },
      { source: "/backend-health", destination: `${api}/health` },
    ];
  },
};
