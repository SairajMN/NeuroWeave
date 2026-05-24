import { motion } from 'framer-motion';
import { useStore } from '../store/useStore';
import type { Phase } from '../types';

const PHASE_COLORS: Record<Phase, string> = {
  idle: '#8888AA',
  perception: '#FFD700',
  decision: '#00F0FF',
  action: '#FF3355',
  memory: '#9D4EDD',
  synthesis: '#00FF88',
  complete: '#00FF88',
  error: '#FF3355',
};

export default function TopologyBar() {
  const nodeCount = useStore((s) => s.nodeCount);
  const edgeCount = useStore((s) => s.edgeCount);
  const statusText = useStore((s) => s.statusText);
  const currentPhase = useStore((s) => s.currentPhase);
  const confidence = useStore((s) => s.confidence);

  const color = PHASE_COLORS[currentPhase] || '#8888AA';

  return (
    <div className="topology-bar">
      <div className="topology-left">
        <div className="system-logo">NEUROWEAVE</div>
        <motion.div
          className="system-status"
          style={{
            borderColor: color,
            color,
            textShadow: `0 0 10px ${color}44`,
          }}
          animate={{
            opacity: currentPhase === 'idle' || currentPhase === 'complete' ? 0.7 : [0.5, 1, 0.5],
          }}
          transition={{ duration: 2, repeat: Infinity }}
        >
          <span className="status-dot" style={{ backgroundColor: color }} />
          {statusText}
        </motion.div>
      </div>

      <div className="topology-center">
        <div className="metric">
          <span className="metric-value">{nodeCount}</span>
          <span className="metric-label">NODES</span>
        </div>
        <div className="metric-divider">·</div>
        <div className="metric">
          <span className="metric-value">{edgeCount}</span>
          <span className="metric-label">EDGES</span>
        </div>
      </div>

      <div className="topology-right">
        <div className="confidence-gauge">
          <svg width="40" height="40" viewBox="0 0 40 40">
            <circle
              cx="20"
              cy="20"
              r="16"
              fill="none"
              stroke="#222"
              strokeWidth="3"
            />
            <motion.circle
              cx="20"
              cy="20"
              r="16"
              fill="none"
              stroke={color}
              strokeWidth="3"
              strokeDasharray={`${2 * Math.PI * 16}`}
              strokeDashoffset={`${2 * Math.PI * 16 * (1 - confidence)}`}
              strokeLinecap="round"
              transform="rotate(-90 20 20)"
              animate={{ strokeDashoffset: `${2 * Math.PI * 16 * (1 - confidence)}` }}
              transition={{ duration: 0.8, ease: 'easeOut' }}
            />
          </svg>
          <span className="confidence-text" style={{ color }}>
            {(confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>
    </div>
  );
}