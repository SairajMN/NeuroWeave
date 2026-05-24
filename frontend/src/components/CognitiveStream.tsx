import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useStore } from '../store/useStore';
import type { TelemetryEvent } from '../types';

const PHASE_COLORS: Record<string, string> = {
  perception: '#FFD700',
  decision: '#00F0FF',
  action: '#FF3355',
  memory: '#9D4EDD',
  synthesis: '#00FF88',
  complete: '#00FF88',
  error: '#FF3355',
};

function getPhaseFromEvent(event: TelemetryEvent): string {
  const p = event.phase;
  if (p.startsWith('perception')) return 'PERCEPTION';
  if (p.startsWith('decision')) return 'DECISION';
  if (p.startsWith('action')) return 'ACTION';
  if (p.startsWith('memory') || p.startsWith('memory_')) return 'MEMORY';
  if (p.startsWith('synthesis') || p === 'complete') return 'SYNTHESIS';
  if (p === 'error' || p === 'loop_warning' || p === 'loop_converged') return 'SYSTEM';
  if (p.startsWith('iteration')) return 'LOOP';
  return 'SYSTEM';
}

function PhaseBadge({ phase }: { phase: string }) {
  const color = PHASE_COLORS[phase.toLowerCase()] || '#8888AA';
  return (
    <span
      className="phase-badge"
      style={{
        borderColor: color,
        color,
        textShadow: `0 0 8px ${color}44`,
      }}
    >
      {phase}
    </span>
  );
}

function EventCard({ event }: { event: TelemetryEvent }) {
  const phase = getPhaseFromEvent(event);
  const phaseLower = phase.toLowerCase();

  let summary = event.phase;
  let details = '';

  if (event.payload) {
    if (event.payload.thought) {
      details = event.payload.thought as string;
      summary = 'REASONING';
    } else if (event.payload.iteration !== undefined) {
      summary = `Iteration ${event.payload.iteration}`;
    } else if (event.payload.tool_call) {
      const tc = event.payload.tool_call as Record<string, unknown>;
      summary = `TOOL: ${tc.name as string}`;
      details = JSON.stringify(tc.arguments, null, 2);
    } else if (event.payload.result) {
      summary = 'TOOL RESULT';
      const res = event.payload.result as Record<string, unknown>;
      details = (res.output_preview as string) || (res.tool_name as string) || '';
    } else if (event.payload.recalled_facts) {
      const facts = event.payload.recalled_facts as string[];
      summary = `Memory Recall (${facts.length} facts)`;
      details = facts.join('\n');
    } else if (event.payload.new_facts_extracted) {
      const facts = event.payload.new_facts_extracted as string[];
      summary = `Extracted ${facts.length} facts`;
      details = facts.join('\n');
    } else if (event.payload.reason) {
      details = event.payload.reason as string;
    } else if (event.payload.warning) {
      details = event.payload.warning as string;
    } else if (event.payload.message) {
      details = event.payload.message as string;
    } else if (event.payload.query) {
      summary = `Query: ${(event.payload.query as string).slice(0, 80)}`;
    }
  }

  return (
    <motion.div
      className="event-card"
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="event-header">
        <PhaseBadge phase={phase} />
        <span className="event-summary">{summary}</span>
      </div>
      {details && (
        <pre className="event-details">
          {details.length > 300 ? `${details.slice(0, 300)}...` : details}
        </pre>
      )}
    </motion.div>
  );
}

export default function CognitiveStream() {
  const telemetryLogs = useStore((s) => s.telemetryLogs);
  const isReasoning = useStore((s) => s.isReasoning);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [telemetryLogs.length]);

  return (
    <div className="cognitive-stream">
      <div className="stream-header">
        <div className="stream-title">COGNITIVE STREAM</div>
        <div className="stream-count">{telemetryLogs.length} events</div>
      </div>

      <div className="stream-events">
        <AnimatePresence>
          {telemetryLogs.map((event, i) => (
            <EventCard key={`${event.phase}-${i}`} event={event} />
          ))}
        </AnimatePresence>

        {isReasoning && (
          <motion.div
            className="event-card thinking"
            initial={{ opacity: 0 }}
            animate={{ opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          >
            <span className="thinking-dots">Processing</span>
          </motion.div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}