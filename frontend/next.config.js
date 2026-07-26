/** @type {import('next').NextConfig} */
const nextConfig = {
  // Produces a minimal self-contained server bundle for the Docker image.
  output: "standalone",
  reactStrictMode: true,

  // Dev only: proxy /api/* to the local FastAPI backend so `npm run dev` works
  // without Docker/Caddy. In production Caddy handles /api, so this is inert.
  async rewrites() {
    if (process.env.NODE_ENV === "production") return [];
    const target = process.env.BACKEND_ORIGIN || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${target}/:path*` }];
  },
};

module.exports = nextConfig;
