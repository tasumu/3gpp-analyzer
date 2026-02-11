import type { NextConfig } from "next";

const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,

  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          // HSTS - Force HTTPS (1 year)
          {
            key: "Strict-Transport-Security",
            value: "max-age=31536000; includeSubDomains; preload",
          },
          // Prevent MIME sniffing
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          // Prevent Clickjacking
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          // Referrer Policy
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          // Content Security Policy
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://accounts.google.com https://www.gstatic.com https://apis.google.com",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com",
              "img-src 'self' data: https:",
              "connect-src 'self' https://*.googleapis.com https://*.firebaseio.com wss://*.firebaseio.com https://*.cloudfunctions.net https://*.run.app",
              "frame-src 'self' https://accounts.google.com https://apis.google.com",
              "object-src 'none'",
              "base-uri 'self'",
              "form-action 'self'",
              "frame-ancestors 'none'",
            ].join("; "),
          },
          // Permissions Policy
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
          },
        ],
      },
    ];
  },

  async rewrites() {
    // Proxy /api/* to the backend API
    // In production, NEXT_PUBLIC_API_URL points to Cloud Run backend
    // In development, defaults to localhost:8000
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/:path*`,
      },
      // Proxy Firebase Auth handler so the auth flow stays first-party.
      // This avoids cross-origin / third-party cookie issues with signInWithRedirect.
      ...(process.env.FIREBASE_AUTH_PROXY_DOMAIN
        ? [
            {
              source: "/__/auth/:path*",
              destination: `https://${process.env.FIREBASE_AUTH_PROXY_DOMAIN}/__/auth/:path*`,
            },
          ]
        : []),
    ];
  },
};

export default nextConfig;
