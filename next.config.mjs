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
      }
    ]
  },
  experimental: {
    serverComponentsExternalPackages: ["duckdb", "duckdb-async"]
  }
};

export default nextConfig;
