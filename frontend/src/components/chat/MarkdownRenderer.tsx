"use client";
import ReactMarkdown from "react-markdown";
import { codeToHtml } from "shiki";
import { use, Suspense } from "react";
import { CitationChip } from "./CitationChip";
import type { Components } from "react-markdown";
import { cn } from "@/lib/utils";
import type { Citation } from "@/types";

interface MarkdownRendererProps {
  content: string;
  citations?: Citation[];
  isStreaming?: boolean;
}

function processContentWithCitations(content: string, citations?: Citation[]): string {
  if (!citations?.length) return content;
  // Replace [1], [2] etc with citation markers
  return content.replace(/\[(\d+)\]/g, (match, num) => {
    const id = parseInt(num);
    if (citations.find((c) => c.id === id)) {
      return `[CITE:${id}]`;
    }
    return match;
  });
}

async function SyntaxHighlighter({ code, lang }: { code: string; lang: string }) {
  try {
    const html = await codeToHtml(code, {
      lang: lang || "plaintext",
      theme: "github-dark-dimmed",
    });
    return (
      <div
        className="shiki-wrapper my-3"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    );
  } catch {
    return (
      <pre className="shiki my-3">
        <code>{code}</code>
      </pre>
    );
  }
}

function InlineCode({ children }: { children: string }) {
  return (
    <code className="font-mono text-[0.8em] px-1 py-0.5 rounded bg-white/[0.07] text-white/80">
      {children}
    </code>
  );
}

function parseCitations(text: string, citations?: Citation[]): React.ReactNode[] {
  if (!citations?.length) return [text];
  const parts = text.split(/(\[CITE:\d+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/\[CITE:(\d+)\]/);
    if (match) {
      return <CitationChip key={i} id={parseInt(match[1])} />;
    }
    return part;
  });
}

const markdownComponents = (citations?: Citation[]): Components => ({
  h1: ({ children }) => (
    <h1 className="text-lg font-semibold text-white mt-4 mb-2">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-base font-semibold text-white mt-3 mb-1.5">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-sm font-semibold text-white/90 mt-2.5 mb-1">{children}</h3>
  ),
  p: ({ children }) => {
    const childrenStr = typeof children === "string" ? children : "";
    return (
      <p className="text-[0.875rem] text-white/80 leading-relaxed mb-3">
        {typeof children === "string"
          ? parseCitations(children, citations)
          : children}
      </p>
    );
  },
  ul: ({ children }) => (
    <ul className="list-disc list-inside space-y-1 mb-3 text-[0.875rem] text-white/75 pl-2">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-inside space-y-1 mb-3 text-[0.875rem] text-white/75 pl-2">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-[var(--color-accent)] pl-3 my-2 text-white/50 italic">
      {children}
    </blockquote>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-[var(--color-accent)] hover:underline"
    >
      {children}
    </a>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-white/90">{children}</strong>
  ),
  em: ({ children }) => <em className="italic text-white/70">{children}</em>,
  hr: () => <hr className="border-[var(--color-border)] my-4" />,
  code: ({ className, children, ...props }) => {
    const isBlock = className?.startsWith("language-");
    const lang = className?.replace("language-", "") ?? "plaintext";
    const code = String(children).replace(/\n$/, "");

    if (isBlock) {
      return <CodeBlock code={code} lang={lang} />;
    }
    return <InlineCode>{code}</InlineCode>;
  },
});

function CodeBlock({ code, lang }: { code: string; lang: string }) {
  return (
    <Suspense
      fallback={
        <pre className="shiki my-3">
          <code>{code}</code>
        </pre>
      }
    >
      <SyntaxHighlighterClient code={code} lang={lang} />
    </Suspense>
  );
}

function SyntaxHighlighterClient({ code, lang }: { code: string; lang: string }) {
  const html = use(
    codeToHtml(code, { lang: lang || "plaintext", theme: "github-dark-dimmed" }).catch(
      () => `<pre class="shiki"><code>${code}</code></pre>`
    )
  );
  return (
    <div className="shiki-wrapper my-3" dangerouslySetInnerHTML={{ __html: html }} />
  );
}

export function MarkdownRenderer({ content, citations, isStreaming }: MarkdownRendererProps) {
  const processed = processContentWithCitations(content, citations);

  return (
    <div className={cn("prose-content", isStreaming && "stream-underline")}>
      <ReactMarkdown components={markdownComponents(citations)}>
        {processed}
      </ReactMarkdown>
    </div>
  );
}
