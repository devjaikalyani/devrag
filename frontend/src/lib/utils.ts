import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNow } from "date-fns";
import type { FaithfulnessInfo } from "@/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function relativeTime(iso: string): string {
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true });
  } catch {
    return iso;
  }
}

export function repoKeyFromUrl(url: string): string {
  try {
    const u = new URL(url);
    const parts = u.pathname.split("/").filter(Boolean);
    if (parts.length >= 2) return `${parts[0]}__${parts[1]}`;
    return parts[parts.length - 1] || url;
  } catch {
    return url.replace(/[^a-zA-Z0-9]/g, "_");
  }
}

export function repoDisplayName(key: string): { name: string; owner: string } {
  const parts = key.split("__");
  if (parts.length >= 2) {
    return { owner: parts[0], name: parts[1] };
  }
  return { owner: "", name: key };
}

export function fileLanguage(filePath: string): string {
  const ext = filePath.split(".").pop()?.toLowerCase() ?? "";
  const map: Record<string, string> = {
    ts: "typescript", tsx: "tsx", js: "javascript", jsx: "jsx",
    py: "python", rs: "rust", go: "go", java: "java",
    cpp: "cpp", c: "c", cs: "csharp", rb: "ruby",
    php: "php", swift: "swift", kt: "kotlin",
    html: "html", css: "css", scss: "scss",
    json: "json", yaml: "yaml", yml: "yaml",
    md: "markdown", sh: "bash", toml: "toml",
  };
  return map[ext] ?? "plaintext";
}

export function faithfulnessInfo(score: number | null, isFaithful: boolean | null): FaithfulnessInfo {
  if (score === null || isFaithful === null) {
    return { score: 0, is_faithful: false, level: "low", label: "Unknown" };
  }
  if (score >= 0.75 && isFaithful) {
    return { score, is_faithful: true, level: "verified", label: "Verified" };
  }
  if (score >= 0.5) {
    return { score, is_faithful: isFaithful, level: "partial", label: "Partially supported" };
  }
  return { score, is_faithful: false, level: "low", label: "Low confidence" };
}

export function truncatePath(path: string, maxLen = 52): string {
  if (path.length <= maxLen) return path;
  const parts = path.split("/");
  if (parts.length <= 2) return "…" + path.slice(-(maxLen - 1));
  return parts[0] + "/…/" + parts.slice(-2).join("/");
}

export function generateId(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function parseBreadcrumb(filePath: string): { dir: string; file: string } {
  const parts = filePath.split("/");
  const file = parts.pop() ?? filePath;
  const dir = parts.join("/");
  return { dir, file };
}
