import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import { useStore } from '../store/useStore';
import { CheckCircle, ExternalLink, Minimize2, Maximize2 } from 'lucide-react';

export default function FinalAnswerRenderer() {
  const finalAnswer = useStore((s) => s.finalAnswer);
  const error = useStore((s) => s.error);
  const [minimized, setMinimized] = useState(false);

  if (!finalAnswer && !error) return null;

  if (minimized) {
    return (
      <button className="fa-minimized-button" onClick={() => setMinimized(false)}>
        <CheckCircle size={14} className="fa-mini-icon" />
        <span className="fa-mini-text">
          Synthesis · {(finalAnswer?.confidence ?? 0) * 100}%
        </span>
        <Maximize2 size={12} />
      </button>
    );
  }

  return (
    <motion.div
      className="final-answer-panel"
      initial={{ opacity: 0, y: 50 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
    >
      <div className="fa-header">
        <CheckCircle size={20} className="fa-icon" />
        <span className="fa-title">SYNTHESIS COMPLETE</span>
        <button className="fa-minimize-btn" onClick={() => setMinimized(true)}>
          <Minimize2 size={14} />
        </button>
      </div>

      {finalAnswer && (
        <div className="fa-body">
          <div className="fa-confidence">
            Confidence: {(finalAnswer.confidence * 100).toFixed(0)}%
          </div>
          
          <div className="fa-markdown">
            <ReactMarkdown>{finalAnswer.answer}</ReactMarkdown>
          </div>

          {finalAnswer.evidence.length > 0 && (
            <div className="fa-evidence">
              <div className="fa-evidence-title">Supporting Evidence</div>
              {finalAnswer.evidence.map((ev, i) => (
                <div key={i} className="fa-evidence-item">
                  <div className="fa-evidence-fact">{ev.fact}</div>
                  <div className="fa-evidence-meta">
                    {ev.source_url && (
                      <a
                        href={ev.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="fa-evidence-link"
                      >
                        <ExternalLink size={12} />
                        Source
                      </a>
                    )}
                    {ev.source_node && (
                      <span className="fa-evidence-node">Node: {ev.source_node}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {finalAnswer.reasoning_path.length > 0 && (
            <div className="fa-reasoning">
              <div className="fa-reasoning-title">Reasoning Path</div>
              <ol className="fa-reasoning-list">
                {finalAnswer.reasoning_path.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}