import type { NextConfig } from "next";

// Static export: the demo is plain files, so it deploys to Vercel or any static host
// and needs no API key. All data in public/demo comes from `elicitsense export-demo`.
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
