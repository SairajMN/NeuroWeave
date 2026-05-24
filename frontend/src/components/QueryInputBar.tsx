import { useState } from 'react';
import { useStore } from '../store/useStore';
import { Send, RefreshCw, History, AlertCircle } from 'lucide-react';

export default function QueryInputBar() {
  const [query, setQuery] = useState('');
  const submitQuery = useStore((s) => s.submitQuery);
  const resetSystem = useStore((s) => s.resetSystem);
  const setShowHistory = useStore((s) => s.setShowHistory);
  const isReasoning = useStore((s) => s.isReasoning);
  const error = useStore((s) => s.error);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isReasoning) return;
    await submitQuery(query.trim());
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      handleSubmit(e);
    }
  };

  return (
    <div className="query-bar-container">
      {error && (
        <div className="error-banner">
          <AlertCircle size={14} />
          <span>{error}</span>
          <button onClick={() => useStore.getState().setCurrentPhase('idle')}>
            ×
          </button>
        </div>
      )}

      <form className="query-bar" onSubmit={handleSubmit}>
        <div className="query-input-wrapper">
          <input
            type="text"
            className="query-input"
            placeholder="Enter your research query..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isReasoning}
          />
        </div>

        <button
          type="submit"
          className="btn btn-primary"
          disabled={!query.trim() || isReasoning}
          title="Submit research query"
        >
          <Send size={16} />
          <span>Research</span>
        </button>

        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => setShowHistory(true)}
          title="View run history"
        >
          <History size={16} />
        </button>

        <button
          type="button"
          className="btn btn-danger"
          onClick={resetSystem}
          disabled={isReasoning}
          title="Reset knowledge graph"
        >
          <RefreshCw size={16} />
        </button>
      </form>
    </div>
  );
}