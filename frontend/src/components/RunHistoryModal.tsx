import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import { useStore } from '../store/useStore';

export default function RunHistoryModal() {
  const showHistory = useStore((s) => s.showHistory);
  const setShowHistory = useStore((s) => s.setShowHistory);
  const history = useStore((s) => s.history);

  return (
    <AnimatePresence>
      {showHistory && (
        <motion.div
          className="modal-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={() => setShowHistory(false)}
        >
          <motion.div
            className="modal-content"
            initial={{ scale: 0.9, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.9, opacity: 0, y: 20 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <h2>RUN HISTORY</h2>
              <button className="modal-close" onClick={() => setShowHistory(false)}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              {history.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon">📡</div>
                  <div>No runs recorded yet.</div>
                </div>
              ) : (
                <div className="history-list">
                  {[...history].reverse().map((record, i) => (
                    <div key={record.run_id || i} className="history-card">
                      <div className="history-run-id">
                        Run: {record.run_id}
                      </div>
                      <div className="history-query">{record.query}</div>
                      <div className="history-meta">
                        <span>{record.extracted_facts.length} facts</span>
                        <span>·</span>
                        <span>{record.entities.length} entities</span>
                        <span>·</span>
                        <span>{new Date(record.timestamp).toLocaleString()}</span>
                      </div>
                      {record.extracted_facts.length > 0 && (
                        <div className="history-facts">
                          {record.extracted_facts.slice(0, 3).map((fact, fi) => (
                            <div key={fi} className="history-fact">
                              → {fact}
                            </div>
                          ))}
                          {record.extracted_facts.length > 3 && (
                            <div className="history-more">
                              +{record.extracted_facts.length - 3} more facts
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}