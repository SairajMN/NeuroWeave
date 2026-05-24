import { create } from 'zustand';
import type {
  NeuroWeaveState,
  TelemetryEvent,
  GraphNodeData,
  GraphEdgeData,
  FinalAnswer,
  MemoryRecord,
  Phase,
} from '../types';

const API_BASE = 'http://localhost:8000';

interface NeuroWeaveActions {
  setConnected: (connected: boolean) => void;
  submitQuery: (query: string) => Promise<void>;
  fetchGraph: () => Promise<void>;
  fetchHistory: () => Promise<void>;
  resetSystem: () => Promise<void>;
  appendTelemetry: (event: TelemetryEvent) => void;
  setShowHistory: (show: boolean) => void;
  setCurrentPhase: (phase: Phase) => void;
}

type NeuroWeaveStore = NeuroWeaveState & NeuroWeaveActions;

export const useStore = create<NeuroWeaveStore>((set, get) => ({
  // State
  connected: false,
  runId: null,
  nodes: [],
  edges: [],
  telemetryLogs: [],
  isReasoning: false,
  currentPhase: 'idle',
  finalAnswer: null,
  confidence: 0,
  nodeCount: 0,
  edgeCount: 0,
  statusText: 'INITIALIZING',
  history: [],
  showHistory: false,
  error: null,

  // Actions
  setConnected: (connected) => set({ connected }),

  submitQuery: async (query: string) => {
    const state = get();
    state.error && set({ error: null });

    set({
      isReasoning: true,
      currentPhase: 'perception',
      telemetryLogs: [],
      finalAnswer: null,
      confidence: 0,
      statusText: 'CONNECTING',
    });

    try {
      const response = await fetch(`${API_BASE}/api/research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body stream');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            if (!data || data === ': keep-alive') continue;

            try {
              const event: TelemetryEvent = JSON.parse(data);
              const { appendTelemetry } = get();
              appendTelemetry(event);
            } catch (parseErr) {
              console.warn('SSE parse error:', parseErr);
            }
          }
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      set({ error: msg, isReasoning: false, currentPhase: 'error', statusText: 'ERROR' });
    } finally {
      // Final graph fetch and state cleanup after completion
      set({ isReasoning: false });
      get().fetchGraph();
      get().fetchHistory();
    }
  },

  fetchGraph: async () => {
    try {
      const response = await fetch(`${API_BASE}/api/graph`);
      if (!response.ok) return;
      const data: { nodes: GraphNodeData[]; links: GraphEdgeData[] } = await response.json();
      set({
        nodes: data.nodes || [],
        edges: data.links || [],
        nodeCount: (data.nodes || []).length,
        edgeCount: (data.links || []).length,
      });
    } catch (err) {
      console.warn('Graph fetch error:', err);
    }
  },

  fetchHistory: async () => {
    try {
      const response = await fetch(`${API_BASE}/api/history`);
      if (!response.ok) return;
      const data: { history: MemoryRecord[] } = await response.json();
      set({ history: data.history || [] });
    } catch (err) {
      console.warn('History fetch error:', err);
    }
  },

  resetSystem: async () => {
    try {
      await fetch(`${API_BASE}/api/reset`, { method: 'POST' });
      set({
        nodes: [],
        edges: [],
        telemetryLogs: [],
        isReasoning: false,
        currentPhase: 'idle',
        finalAnswer: null,
        confidence: 0,
        nodeCount: 0,
        edgeCount: 0,
        statusText: 'RESET',
        error: null,
      });
      get().fetchHistory();
    } catch (err) {
      console.warn('Reset error:', err);
    }
  },

  appendTelemetry: (event: TelemetryEvent) => {
    const { telemetryLogs } = get();
    const updated = [...telemetryLogs, event];

    // Update phase based on event
    let phase: Phase = 'idle';
    let status = 'REASONING';
    let confidence = 0;

    if (event.phase === 'perception_start' || event.phase === 'perception_end') {
      phase = 'perception';
    } else if (event.phase === 'decision_start' || event.phase === 'decision_end') {
      phase = 'decision';
    } else if (event.phase === 'action_start' || event.phase === 'action_end') {
      phase = 'action';
    } else if (event.phase === 'memory_recall_start' || event.phase === 'memory_recall_end' || event.phase === 'memory_update_start' || event.phase === 'memory_update_end') {
      phase = 'memory';
    } else if (event.phase === 'synthesis_start') {
      phase = 'synthesis';
    } else if (event.phase === 'synthesis_end') {
      phase = 'complete';
      status = 'CONVERGED';
      const payload = event.payload as Record<string, unknown>;
      if (payload) {
        const answer = payload as unknown as FinalAnswer;
        if (answer.confidence !== undefined) confidence = answer.confidence;
        set({ finalAnswer: answer });
      }
    } else if (event.phase === 'complete') {
      phase = 'complete';
      status = 'CONVERGED';
      const payload = event.payload as unknown as FinalAnswer;
      if (payload) {
        if (payload.confidence !== undefined) confidence = payload.confidence;
        set({ finalAnswer: payload });
      }
    } else if (event.phase === 'error') {
      phase = 'error';
      status = 'ERROR';
    }

    set({
      telemetryLogs: updated,
      currentPhase: phase,
      statusText: status,
      confidence: confidence || get().confidence,
    });

    // Gracefully stop reasoning if complete/error
    if (phase === 'complete' || phase === 'error') {
      set({ isReasoning: false });
    }
  },

  setShowHistory: (show) => set({ showHistory: show }),
  setCurrentPhase: (phase) => set({ currentPhase: phase }),
}));