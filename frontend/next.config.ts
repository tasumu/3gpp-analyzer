import type { NextConfig } from "next";

const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,

  async rewrites() {
    // Proxy /api/* to the backend API
    // In production, NEXT_PUBLIC_API_URL points to Cloud Run backend
    // In development, defaults to localhost:8000
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
