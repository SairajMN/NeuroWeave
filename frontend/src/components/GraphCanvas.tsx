import { useEffect, useRef, useCallback, useState, useMemo } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import * as THREE from 'three';
import { useStore } from '../store/useStore';
import type { GraphNodeData, GraphEdgeData } from '../types';

interface GraphNode3D {
  id: string;
  label: string;
  type: string;
  confidence: number;
  attributes: Record<string, string>;
  source_urls: string[];
  x?: number;
  y?: number;
  z?: number;
  fx?: number;
  fy?: number;
  fz?: number;
}

interface GraphLink3D {
  source: string | GraphNode3D;
  target: string | GraphNode3D;
  relation: string;
  confidence: number;
  evidence: string;
}

const NODE_COLORS: Record<string, string> = {
  person: '#00F0FF',
  company: '#9D4EDD',
  concept: '#00FF88',
  technology: '#FFD700',
  website: '#FF3355',
  article: '#FF8844',
  event: '#FF66AA',
  fact: '#44CCFF',
};

const getNodeColor = (type: string) => NODE_COLORS[type] || '#8888AA';

function createLabelSprite(node: GraphNode3D, isSelected: boolean): THREE.Sprite {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d')!;

  const label = node.label;
  // Larger font for better readability
  const fontSize = isSelected ? 36 : 28;
  ctx.font = `700 ${fontSize}px Inter, SF Pro Display, -apple-system, sans-serif`;
  const textWidth = ctx.measureText(label).width;

  const padX = 18;
  const padY = 12;
  const width = Math.ceil(textWidth + padX * 2);
  const height = Math.ceil(fontSize + padY * 2);

  canvas.width = width;
  canvas.height = height;

  // Stronger background with shadow
  const radius = 8;
  ctx.shadowColor = 'rgba(0,0,0,0.5)';
  ctx.shadowBlur = 8;
  ctx.shadowOffsetY = 2;
  ctx.fillStyle = isSelected ? 'rgba(0, 240, 255, 0.2)' : 'rgba(0, 0, 0, 0.8)';
  ctx.beginPath();
  ctx.moveTo(radius, 0);
  ctx.lineTo(width - radius, 0);
  ctx.quadraticCurveTo(width, 0, width, radius);
  ctx.lineTo(width, height - radius);
  ctx.quadraticCurveTo(width, height, width - radius, height);
  ctx.lineTo(radius, height);
  ctx.quadraticCurveTo(0, height, 0, height - radius);
  ctx.lineTo(0, radius);
  ctx.quadraticCurveTo(0, 0, radius, 0);
  ctx.closePath();
  ctx.fill();

  // Border
  ctx.shadowBlur = 0;
  ctx.strokeStyle = getNodeColor(node.type);
  ctx.lineWidth = 2;
  ctx.stroke();

  // Glow behind text
  ctx.shadowColor = getNodeColor(node.type);
  ctx.shadowBlur = 12;

  // Text - white with higher contrast
  ctx.fillStyle = '#FFFFFF';
  ctx.font = `700 ${fontSize}px Inter, SF Pro Display, -apple-system, sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(label, width / 2, height / 2);

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;

  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false,
    depthWrite: false,
    sizeAttenuation: true,
  });

  const sprite = new THREE.Sprite(material);
  // Much larger scale
  const scale = isSelected ? 1.2 : 1.0;
  sprite.scale.set(width * (scale / 20), height * (scale / 20), 1);
  // Place further below the sphere to avoid overlap
  sprite.position.y = -(isSelected ? 10 : 7);

  return sprite;
}

export default function GraphCanvas() {
  const nodes = useStore((s) => s.nodes);
  const edges = useStore((s) => s.edges);
  const fgRef = useRef<any>(null);

  const [selectedNode, setSelectedNode] = useState<GraphNode3D | null>(null);
  const [highlightNodes, setHighlightNodes] = useState<Set<string>>(new Set());
  const [highlightLinks, setHighlightLinks] = useState<Set<GraphLink3D>>(new Set());
  const [hoveredNode, setHoveredNode] = useState<GraphNode3D | null>(null);
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const graphData = useMemo(
    () => ({
      nodes: nodes.map(
        (n: GraphNodeData): GraphNode3D => ({
          id: n.id,
          label: n.label,
          type: n.type,
          confidence: n.confidence,
          attributes: n.attributes,
          source_urls: n.source_urls,
        })
      ),
      links: edges.map(
        (e: GraphEdgeData): GraphLink3D => ({
          source: e.source,
          target: e.target,
          relation: e.relation,
          confidence: e.confidence,
          evidence: e.evidence,
        })
      ),
    }),
    [nodes, edges]
  );

  useEffect(() => {
    if (fgRef.current && nodes.length > 0) {
      setTimeout(() => {
        try {
          fgRef.current.zoomToFit(400, 80);
        } catch (_) {}
      }, 300);
    }
  }, [nodes.length]);

  const handleNodeClick = useCallback((node: GraphNode3D) => {
    if (selectedNode?.id === node.id) {
      setSelectedNode(null);
      setHighlightNodes(new Set());
      setHighlightLinks(new Set());
      return;
    }
    setSelectedNode(node);
    const nodeIds = new Set<string>([node.id]);
    const linkSet = new Set<GraphLink3D>();
    graphData.links.forEach((link) => {
      const src = typeof link.source === 'object' ? (link.source as GraphNode3D).id : link.source;
      const tgt = typeof link.target === 'object' ? (link.target as GraphNode3D).id : link.target;
      if (src === node.id) {
        nodeIds.add(tgt);
        linkSet.add(link);
      }
      if (tgt === node.id) {
        nodeIds.add(src);
        linkSet.add(link);
      }
    });
    setHighlightNodes(nodeIds);
    setHighlightLinks(linkSet);
    if (fgRef.current) fgRef.current.emitParticle(node);
  }, [selectedNode, graphData.links]);

  const handleBackgroundClick = useCallback(() => {
    setSelectedNode(null);
    setHighlightNodes(new Set());
    setHighlightLinks(new Set());
  }, []);

  const handleNodeHover = useCallback((node: GraphNode3D | null) => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    if (node) {
      hoverTimeoutRef.current = setTimeout(() => setHoveredNode(node), 200);
    } else {
      setHoveredNode(null);
    }
  }, []);

  const handleNodeDragEnd = useCallback((node: GraphNode3D) => {
    node.fx = node.x;
    node.fy = node.y;
    node.fz = node.z;
  }, []);

  const zoomIn = () => {
    if (fgRef.current) {
      const dir = new THREE.Vector3(0, 0, -1).applyQuaternion(fgRef.current.camera().quaternion);
      fgRef.current.camera().position.addScaledVector(dir, 20);
    }
  };
  const zoomOut = () => {
    if (fgRef.current) {
      const dir = new THREE.Vector3(0, 0, -1).applyQuaternion(fgRef.current.camera().quaternion);
      fgRef.current.camera().position.addScaledVector(dir, -20);
    }
  };
  const resetView = () => {
    if (fgRef.current) {
      try {
        fgRef.current.zoomToFit(400, 80);
      } catch (_) {}
    }
    setSelectedNode(null);
    setHighlightNodes(new Set());
    setHighlightLinks(new Set());
  };
  const unfixAllNodes = () => {
    if (fgRef.current) {
      fgRef.current.graphData().nodes.forEach((n: GraphNode3D) => {
        n.fx = undefined;
        n.fy = undefined;
        n.fz = undefined;
      });
      fgRef.current.d3ReheatSimulation();
    }
  };

  const isNodeHighlighted = (node: GraphNode3D) =>
    highlightNodes.size === 0 || highlightNodes.has(node.id);
  const isLinkHighlighted = (link: GraphLink3D) =>
    highlightLinks.size === 0 || highlightLinks.has(link);
  const isNodeSelected = (node: GraphNode3D) => selectedNode?.id === node.id;

  return (
    <div className="graph-container-wrapper">
      <div className="graph-controls">
        <button onClick={zoomIn} title="Zoom in" className="graph-control-btn">+</button>
        <button onClick={zoomOut} title="Zoom out" className="graph-control-btn">−</button>
        <button onClick={resetView} title="Reset view" className="graph-control-btn">⟲</button>
        <button onClick={unfixAllNodes} title="Release all" className="graph-control-btn">⊘</button>
      </div>

      {selectedNode && (
        <div className="node-info-panel">
          <div className="nip-header">
            <span className="nip-dot" style={{ backgroundColor: getNodeColor(selectedNode.type), boxShadow: `0 0 12px ${getNodeColor(selectedNode.type)}` }} />
            <div className="nip-title-group">
              <div className="nip-label">{selectedNode.label}</div>
              <div className="nip-type">{selectedNode.type}</div>
            </div>
            <button className="nip-close" onClick={() => { setSelectedNode(null); setHighlightNodes(new Set()); setHighlightLinks(new Set()); }}>×</button>
          </div>
          <div className="nip-body">
            <div className="nip-row">
              <span className="nip-row-label">Confidence</span>
              <span className="nip-row-value" style={{ color: '#00FF88' }}>{(selectedNode.confidence * 100).toFixed(0)}%</span>
            </div>
            {Object.keys(selectedNode.attributes).length > 0 && (
              <div className="nip-section">
                <div className="nip-section-title">Attributes</div>
                {Object.entries(selectedNode.attributes).map(([k, v]) => (
                  <div key={k} className="nip-row"><span className="nip-row-label">{k}</span><span className="nip-row-value">{String(v)}</span></div>
                ))}
              </div>
            )}
            {selectedNode.source_urls.length > 0 && (
              <div className="nip-section">
                <div className="nip-section-title">Sources</div>
                {selectedNode.source_urls.map((url, i) => (
                  <a key={i} href={url} target="_blank" rel="noopener noreferrer" className="nip-url">{url.length > 50 ? url.slice(0, 50) + '...' : url}</a>
                ))}
              </div>
            )}
            {/* Connections Summary */}
            <div className="nip-section">
              <div className="nip-section-title">
                Connections ({highlightNodes.size - 1})
              </div>
              {graphData.links
                .filter((link) => {
                  const src = typeof link.source === 'object' ? (link.source as GraphNode3D).id : link.source;
                  const tgt = typeof link.target === 'object' ? (link.target as GraphNode3D).id : link.target;
                  return src === selectedNode.id || tgt === selectedNode.id;
                })
                .map((link, i) => {
                  const src = typeof link.source === 'object' ? (link.source as GraphNode3D).id : link.source;
                  const tgt = typeof link.target === 'object' ? (link.target as GraphNode3D).id : link.target;
                  const other = src === selectedNode.id ? tgt : src;
                  const otherNode = nodes.find((n) => n.id === other);
                  return (
                    <div key={i} className="nip-connection">
                      <div className="nip-conn-header">
                        <span
                          className="nip-conn-dot"
                          style={{ backgroundColor: getNodeColor(otherNode?.type || '') }}
                        />
                        <span className="nip-conn-label">{otherNode?.label || other}</span>
                      </div>
                      <div className="nip-conn-rel">{link.relation}</div>
                      <div className="nip-conn-evidence">{link.evidence}</div>
                    </div>
                  );
                })}
            </div>
          </div>
        </div>
      )}

      {hoveredNode && !selectedNode && (
        <div className="graph-hover-tooltip">
          <div className="ght-header">
            <span className="ght-dot" style={{ backgroundColor: getNodeColor(hoveredNode.type) }} />
            <div className="ght-title-group">
              <div className="ght-label">{hoveredNode.label}</div>
              <div className="ght-type">{hoveredNode.type}</div>
            </div>
          </div>
          <div className="ght-row">
            <span>Confidence</span>
            <span className="ght-val" style={{ color: '#00FF88' }}>{(hoveredNode.confidence * 100).toFixed(0)}%</span>
          </div>
          {Object.keys(hoveredNode.attributes).length > 0 && (
            <div className="ght-row">
              <span>Attributes</span>
              <span className="ght-val">{Object.keys(hoveredNode.attributes).length}</span>
            </div>
          )}
          {hoveredNode.source_urls.length > 0 && (
            <div className="ght-row">
              <span>Sources</span>
              <span className="ght-val">{hoveredNode.source_urls.length}</span>
            </div>
          )}
          <div className="ght-footer">Click to inspect · Drag to reposition</div>
        </div>
      )}

      {nodes.length === 0 ? (
        <div className="graph-empty">
          <div className="graph-empty-icon">◆</div>
          <div className="graph-empty-text">KNOWLEDGE GRAPH EMPTY</div>
          <div className="graph-empty-sub">Submit a query to build the graph</div>
          <div className="graph-empty-hint">Drag nodes freely · Click to inspect · Scroll to zoom</div>
        </div>
      ) : (
        <ForceGraph3D
          ref={fgRef}
          graphData={graphData}
          nodeId="id"
          nodeLabel={null}
          nodeColor={(node: GraphNode3D) =>
            selectedNode
              ? isNodeSelected(node)
                ? getNodeColor(node.type)
                : isNodeHighlighted(node)
                ? getNodeColor(node.type)
                : '#333355'
              : getNodeColor(node.type)
          }
          nodeVal={(node: GraphNode3D) =>
            selectedNode?.id === node.id ? 20 : 6 + node.confidence * 8
          }
          linkColor={(link: GraphLink3D) =>
            selectedNode ? (isLinkHighlighted(link) ? '#00F0FF' : '#222244') : '#00F0FF66'
          }
          linkWidth={(link: GraphLink3D) =>
            selectedNode && isLinkHighlighted(link) ? 3 : 0.5 + link.confidence * 1.5
          }
          linkDirectionalParticles={selectedNode ? ((link: GraphLink3D) => (isLinkHighlighted(link) ? 4 : 0)) : 2}
          linkDirectionalParticleWidth={3}
          linkDirectionalParticleSpeed={0.005}
          linkDirectionalParticleColor={() => '#00F0FF'}
          backgroundColor="#0A0A0C"
          d3AlphaDecay={0.12}
          d3VelocityDecay={0.7}
          d3AlphaMin={0.001}
          warmupTicks={60}
          cooldownTicks={10}
          enableNodeDrag={true}
          enableNavigationControls={true}
          showNavInfo={false}
          onNodeClick={handleNodeClick}
          onNodeHover={handleNodeHover}
          onBackgroundClick={handleBackgroundClick}
          onNodeDragEnd={handleNodeDragEnd}
          rendererConfig={{ antialias: true, alpha: true }}
          nodeThreeObject={(node: GraphNode3D) => {
            const isSel = isNodeSelected(node);
            const isHL = isNodeHighlighted(node);
            const color = new THREE.Color(getNodeColor(node.type));
            const group = new THREE.Group();
            const sphereSize = isSel ? 6 : 3 + node.confidence * 4;

            // Outer glow for selected
            if (isSel) {
              const glow = new THREE.Mesh(
                new THREE.SphereGeometry(sphereSize * 1.3, 24, 24),
                new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.15 })
              );
              group.add(glow);
            }

            // Main sphere
            const sphere = new THREE.Mesh(
              new THREE.SphereGeometry(sphereSize, 32, 32),
              new THREE.MeshStandardMaterial({
                color,
                emissive: color,
                emissiveIntensity: isSel ? 0.9 : 0.2,
                metalness: 0.05,
                roughness: 0.5,
              })
            );
            group.add(sphere);

            // Rings for selected node
            if (isSel) {
              const r1 = new THREE.Mesh(
                new THREE.TorusGeometry(sphereSize + 2, 0.2, 16, 48),
                new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.5 })
              );
              r1.rotation.x = Math.PI / 2;
              group.add(r1);
              const r2 = new THREE.Mesh(
                new THREE.TorusGeometry(sphereSize + 2.5, 0.15, 16, 48),
                new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.3 })
              );
              r2.rotation.z = Math.PI / 3;
              group.add(r2);
            }

            // Dim non-highlighted nodes
            if (!isHL && selectedNode) {
              sphere.material.transparent = true;
              sphere.material.opacity = 0.15;
              sphere.material.needsUpdate = true;
            }

            // Label below sphere
            const label = createLabelSprite(node, isSel);
            group.add(label);

            return group;
          }}
        />
      )}
    </div>
  );
}