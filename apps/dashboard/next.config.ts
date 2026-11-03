import type { NextConfig } from "next";

// Read at build time and baked into the server output (Next 16 has no runtime config).
// Docker passes http://api:8000 as a build arg; local `npm run dev` targets the host API.
const apiUrl = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    // Browser calls /api/v1/* on the dashboard origin; Next proxies them to FastAPI.
    return [{ source: "/api/v1/:path*", destination: `${apiUrl}/api/v1/:path*` }];
  },
};

export default nextConfig;
