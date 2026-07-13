import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  async rewrites() {
    const api = process.env.API_PROXY_TARGET ?? "http://api:8000";
    const auth = process.env.AUTH_PROXY_TARGET ?? "http://auth:4000";
    return [
      {
        source: "/api/:path*",
        destination: `${api}/api/:path*`,
      },
      // In production Caddy routes /auth/* before traffic reaches Next; this
      // rewrite covers local dev and the container's direct port.
      {
        source: "/auth/:path*",
        destination: `${auth}/auth/:path*`,
      },
    ];
  },
};

export default nextConfig;
