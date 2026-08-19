/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,

  // Dev only: proxy /papi/* to the local control-plane API so `npm run dev`
  // works without Docker. In production Caddy handles the prefix.
  // The path is deliberately NOT /api — the operator console and a tenant
  // workspace must never be able to talk to each other's backend by accident.
  async rewrites() {
    if (process.env.NODE_ENV === "production") return [];
    const target = process.env.CONTROL_PLANE_ORIGIN || "http://localhost:8100";
    return [{ source: "/papi/:path*", destination: `${target}/:path*` }];
  },
};

module.exports = nextConfig;
