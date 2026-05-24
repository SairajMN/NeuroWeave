// NeuroWeave Frontend Type Definitions

export interface GraphNodeData {
  id: string;
  type: string;
  label: string;
  attributes: Record<string, string>;
  source_urls: string[];
  confidence: number;
  created_run_id: string;
}

export interface GraphEdgeData {
  source: string;
  target: string;
  relation: string;
  evidence: string;
  confidence: number;
  created_run_id: string;
}

export interface AnswerEvidence {
  fact: string;
  source_node: string | null;
  source_url: string | null;
}

export interface FinalAnswer {
  query: string;
  answer: string;
  confidence: number;
  evidence: AnswerEvidence[];
  reasoning_path: string[];
}

export interface TelemetryEvent {
  phase: string;
  payload: Record<string, unknown>;
}

export interface MemoryRecord {
  run_id: string;
  query: string;
  extracted_facts: string[];
  entities: string[];
  timestamp: string;
}

export type Phase =
  | 'idle'
  | 'perception'
  | 'decision'
  | 'action'
  | 'memory'
  | 'synthesis'
  | 'complete'
  | 'error';

export interface NeuroWeaveState {
  connected: boolean;
  runId: string | null;
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  telemetryLogs: TelemetryEvent[];
  isReasoning: boolean;
  currentPhase: Phase;
  finalAnswer: FinalAnswer | null;
  confidence: number;
  nodeCount: number;
  edgeCount: number;
  statusText: string;
  history: MemoryRecord[];
  showHistory: boolean;
  error: string | null;
}