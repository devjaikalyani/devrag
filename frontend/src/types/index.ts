export interface Repo {
  key: string;
  name: string;
  owner?: string;
  url?: string;
  path?: string;
  fileCount?: number;
  chunkCount: number;
  lastIndexed: string; // ISO date
  isActive: boolean;
}

export interface Source {
  source: string;       // file path
  start_line?: number;
  end_line?: number;
  language?: string;
  rerank_score: number;
  dense_score?: number;
  sparse_score?: number;
  text_preview: string;
  chunk_id?: string;
}

export interface FaithfulnessInfo {
  score: number;           // 0-1
  is_faithful: boolean;
  level: "verified" | "partial" | "low";
  label: string;
  flagged_sentences?: string[];
}

export interface Citation {
  id: number;
  source: Source;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  citations?: Citation[];
  faithfulness?: FaithfulnessInfo;
  isStreaming?: boolean;
  sources?: Source[];
  activeRepo?: string;
  messageId?: string;
}

export interface ChatSession {
  id: string;
  repoKey: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
}

export interface QueryResponse {
  question: string;
  answer: string;
  sources: Source[];
  faithfulness_score: number | null;
  is_faithful: boolean | null;
  active_repo: string | null;
}

export interface IngestProgress {
  status: "idle" | "cloning" | "chunking" | "embedding" | "bm25" | "done" | "error";
  message: string;
  chunks_parsed?: number;
  embeddings_done?: number;
  error?: string;
}

export interface IngestedSource {
  key: string;
  type: "github" | "local" | "text" | string;
  identifier: string;
  display_name: string;
  chunk_count: number;
  ingested_at: string;
}

export interface IndexStats {
  total_chunks: number;
  index_loaded: boolean;
  active_key: string | null;
  ingested_sources: IngestedSource[];
}

export interface TraceData {
  message_id: string;
  embed_ms: number;
  retrieve_ms: number;
  rerank_ms: number;
  generate_ms: number;
  nli_ms: number;
  total_ms: number;
  rewritten_query?: string;
  dense_rank?: RRFRow[];
}

export interface RRFRow {
  chunk_id: string;
  file: string;
  dense_rank: number;
  bm25_rank: number;
  fused_rank: number;
  rerank_score: number;
}

export type RightPanelTab = "sources" | "retrieval" | "trace";
