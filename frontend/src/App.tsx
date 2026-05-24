import { useEffect } from 'react';
import { useStore } from './store/useStore';
import TopologyBar from './components/TopologyBar';
import CognitiveStream from './components/CognitiveStream';
import GraphCanvas from './components/GraphCanvas';
import QueryInputBar from './components/QueryInputBar';
import FinalAnswerRenderer from './components/FinalAnswerRenderer';
import RunHistoryModal from './components/RunHistoryModal';

export default function App() {
  const fetchGraph = useStore((s) => s.fetchGraph);
  const fetchHistory = useStore((s) => s.fetchHistory);
  const setConnected = useStore((s) => s.setConnected);

  useEffect(() => {
    // Initial data load
    fetchGraph();
    fetchHistory();
    setConnected(true);
  }, []);

  return (
    <div className="app-container">
      <TopologyBar />

      <div className="app-main">
        <div className="panel-left">
          <CognitiveStream />
        </div>

        <div className="panel-right">
          <div className="graph-container">
            <GraphCanvas />
          </div>
        </div>
      </div>

      <FinalAnswerRenderer />
      <QueryInputBar />
      <RunHistoryModal />
    </div>
  );
}