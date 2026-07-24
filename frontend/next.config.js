/** @type {import('next').NextConfig} */
const nextConfig = {
  // Produces a minimal self-contained server bundle for the Docker image.
  output: "standalone",
  reactStrictMode: true,
};

module.exports = nextConfig;
