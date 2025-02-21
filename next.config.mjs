/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "ui.shadcn.com"
      },
      {
        protocol: "https",
        hostname: "duckdb.org"
      },
      {
        protocol: "https",
        hostname: "nextjs.org"
      },
      {
        protocol: "https",
        hostname: "bun.sh"
      }
    ]
  },
  experimental: {
    serverComponentsExternalPackages: ["duckdb", "duckdb-async"]
  }
};

export default nextConfig;
