import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output is required by frontend/Dockerfile (it copies
  // .next/standalone). The Docker build sets DOCKER_BUILD=1; Vercel and
  // local builds leave it unset and get the normal output.
  output: process.env.DOCKER_BUILD === "1" ? "standalone" : undefined,
};

export default nextConfig;
