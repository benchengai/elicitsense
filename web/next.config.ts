import type { NextConfig } from "next";

// Static export: the demo is plain files, so it deploys to Vercel or any static host
// and needs no API key. All data in public/demo comes from `elicitsense export-demo`.
// DEMO_BASE_PATH serves it from a sub-path, e.g. /demos/elicitsense on a personal site.
const basePath = process.env.DEMO_BASE_PATH ?? "";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  basePath,
  env: { NEXT_PUBLIC_BASE_PATH: basePath },
};

export default nextConfig;
