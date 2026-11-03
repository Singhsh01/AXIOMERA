/** @type {import('next').NextConfig} */
const api = process.env.ORKESTR_API_URL || "http://localhost:8000";
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
