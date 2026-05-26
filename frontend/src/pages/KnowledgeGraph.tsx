import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import Card from '../components/Card';
import Loading from '../components/Loading';
import { getKnowledgeGraph } from '../api/knowledgeGraph';
import type { KnowledgeGraph as KGType, KGNode, KGEdge } from '../types';

const NODE_COLORS: Record<string, string> = {
  concept: '#3B82F6',
  chapter: '#10B981',
  knowledge_unit: '#8B5CF6',
};

const FILTER_OPTIONS = [
  { value: 'all', label: '全部', icon: '🔵' },
  { value: 'concept', label: '概念', icon: '💎' },
  { value: 'chapter', label: '章节', icon: '📑' },
  { value: 'knowledge_unit', label: '知识单元', icon: '🧩' },
];

// ---- 力导向布局引擎（零依赖） ----
interface SimNode {
  id: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  color: string;
  label: string;
  node_type: string;
  mastery_score?: number;
}

interface SimEdge {
  source: string;
  target: string;
  weight: number;
  relation_type: string;
}

function runForceLayout(
  nodes: SimNode[],
  edges: SimEdge[],
  width: number,
  height: number,
  iterations: number = 300,
) {
  const nodeMap = new Map<string, SimNode>();
  nodes.forEach((n) => nodeMap.set(n.id, n));

  // 初始化随机位置（围绕中心）
  const cx = width / 2;
  const cy = height / 2;
  nodes.forEach((n) => {
    if (n.x === 0 && n.y === 0) {
      n.x = cx + (Math.random() - 0.5) * 200;
      n.y = cy + (Math.random() - 0.5) * 200;
    }
  });

  const repulsion = 8000;    // 节点间斥力
  const attraction = 0.005;  // 边引力
  const damping = 0.9;       // 速度衰减
  const idealLen = 150;      // 理想边长

  for (let iter = 0; iter < iterations; iter++) {
    // 1. 斥力：所有节点两两排斥
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = repulsion / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        a.vx -= fx;
        a.vy -= fy;
        b.vx += fx;
        b.vy += fy;
      }
    }

    // 2. 引力：边连接的节点相互吸引
    for (const edge of edges) {
      const a = nodeMap.get(edge.source);
      const b = nodeMap.get(edge.target);
      if (!a || !b) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (dist - idealLen) * attraction;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      a.vx += fx;
      a.vy += fy;
      b.vx -= fx;
      b.vy -= fy;
    }

    // 3. 中心引力（防止飞散）
    for (const n of nodes) {
      n.vx += (cx - n.x) * 0.001;
      n.vy += (cy - n.y) * 0.001;
    }

    // 4. 更新位置
    for (const n of nodes) {
      n.vx *= damping;
      n.vy *= damping;
      n.x += n.vx;
      n.y += n.vy;
      // 边界约束
      n.x = Math.max(50, Math.min(width - 50, n.x));
      n.y = Math.max(50, Math.min(height - 50, n.y));
    }
  }
}

export default function KnowledgeGraph() {
  const { bookId } = useParams<{ bookId: string }>();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [graph, setGraph] = useState<KGType | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<KGNode | null>(null);
  const [filter, setFilter] = useState<string>('all');
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  // 力导向计算后的节点位置
  const simNodesRef = useRef<SimNode[]>([]);
  const simEdgesRef = useRef<SimEdge[]>([]);
  const nodePosMapRef = useRef<Map<string, { x: number; y: number }>>(new Map());

  useEffect(() => {
    if (bookId) loadGraph();
  }, [bookId]);

  useEffect(() => {
    if (graph) {
      computeLayout();
      drawGraph();
    }
  }, [graph, transform, filter]);

  const loadGraph = async () => {
    try {
      const data = await getKnowledgeGraph(bookId!);
      setGraph(data);
    } catch (error) {
      console.error('加载知识图谱失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const computeLayout = useCallback(() => {
    if (!graph || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const width = canvas.offsetWidth;
    const height = canvas.offsetHeight;

    const filteredNodes =
      filter === 'all' ? graph.nodes : graph.nodes.filter((n) => n.node_type === filter);
    const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));

    const filteredEdges = graph.edges.filter(
      (e) => filteredNodeIds.has(e.source_id) && filteredNodeIds.has(e.target_id),
    );

    const simNodes: SimNode[] = filteredNodes.map((n) => ({
      id: n.id,
      x: nodePosMapRef.current.get(n.id)?.x ?? 0,
      y: nodePosMapRef.current.get(n.id)?.y ?? 0,
      vx: 0,
      vy: 0,
      size: n.size * 8 + 12,  // 视觉大小
      color: n.color || NODE_COLORS[n.node_type] || '#6B7280',
      label: n.label,
      node_type: n.node_type,
      mastery_score: n.mastery_score,
    }));

    const simEdges: SimEdge[] = filteredEdges.map((e) => ({
      source: e.source_id,
      target: e.target_id,
      weight: e.weight,
      relation_type: e.relation_type,
    }));

    runForceLayout(simNodes, simEdges, width, height, 300);

    // 保存计算结果
    simNodesRef.current = simNodes;
    simEdgesRef.current = simEdges;
    const posMap = new Map<string, { x: number; y: number }>();
    simNodes.forEach((n) => posMap.set(n.id, { x: n.x, y: n.y }));
    nodePosMapRef.current = posMap;
  }, [graph, filter]);

  const drawGraph = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 2;
    const width = canvas.offsetWidth;
    const height = canvas.offsetHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    ctx.save();
    ctx.translate(transform.x, transform.y);
    ctx.scale(transform.scale, transform.scale);

    const posMap = nodePosMapRef.current;

    // 画边
    simEdgesRef.current.forEach((edge) => {
      const sourcePos = posMap.get(edge.source);
      const targetPos = posMap.get(edge.target);
      if (!sourcePos || !targetPos) return;

      ctx.beginPath();
      ctx.moveTo(sourcePos.x, sourcePos.y);
      ctx.lineTo(targetPos.x, targetPos.y);

      // depends_on 画箭头
      if (edge.relation_type === 'depends_on') {
        ctx.strokeStyle = '#F59E0B';
        ctx.lineWidth = 2;
        ctx.setLineDash([]);
      } else if (edge.relation_type === 'similar_to') {
        ctx.strokeStyle = '#93C5FD';
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);
      } else if (edge.relation_type === 'part_of') {
        ctx.strokeStyle = '#A7F3D0';
        ctx.lineWidth = 1;
        ctx.setLineDash([]);
      } else {
        ctx.strokeStyle = '#E5E7EB';
        ctx.lineWidth = 1;
        ctx.setLineDash([]);
      }
      ctx.stroke();
      ctx.setLineDash([]);

      // depends_on 箭头
      if (edge.relation_type === 'depends_on') {
        const angle = Math.atan2(targetPos.y - sourcePos.y, targetPos.x - sourcePos.x);
        const arrowLen = 10;
        const arrowX = targetPos.x - Math.cos(angle) * 15;
        const arrowY = targetPos.y - Math.sin(angle) * 15;
        ctx.beginPath();
        ctx.moveTo(arrowX, arrowY);
        ctx.lineTo(arrowX - arrowLen * Math.cos(angle - 0.4), arrowY - arrowLen * Math.sin(angle - 0.4));
        ctx.lineTo(arrowX - arrowLen * Math.cos(angle + 0.4), arrowY - arrowLen * Math.sin(angle + 0.4));
        ctx.closePath();
        ctx.fillStyle = '#F59E0B';
        ctx.fill();
      }
    });

    // 画节点
    simNodesRef.current.forEach((node) => {
      const pos = posMap.get(node.id);
      if (!pos) return;

      // 节点圆
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, node.size / 2, 0, Math.PI * 2);
      ctx.fillStyle = node.color;
      ctx.fill();

      // 选中高亮
      if (selectedNode?.id === node.id) {
        ctx.strokeStyle = '#1F2937';
        ctx.lineWidth = 3;
        ctx.stroke();
      }

      // 标签
      ctx.fillStyle = '#374151';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(node.label, pos.x, pos.y + node.size / 2 + 16);
    });

    ctx.restore();
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - transform.x, y: e.clientY - transform.y });
  };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setTransform((prev) => ({ ...prev, x: e.clientX - dragStart.x, y: e.clientY - dragStart.y }));
  };
  const handleMouseUp = () => setIsDragging(false);
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setTransform((prev) => ({ ...prev, scale: Math.max(0.3, Math.min(3, prev.scale * delta)) }));
  };

  const handleClick = (e: React.MouseEvent) => {
    if (!graph || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left - transform.x) / transform.scale;
    const y = (e.clientY - rect.top - transform.y) / transform.scale;

    const filteredNodes =
      filter === 'all' ? graph.nodes : graph.nodes.filter((n) => n.node_type === filter);

    for (const node of filteredNodes) {
      const pos = nodePosMapRef.current.get(node.id);
      if (!pos) continue;
      const distance = Math.sqrt((x - pos.x) ** 2 + (y - pos.y) ** 2);
      if (distance <= node.size * 8 / 2 + 5) {
        setSelectedNode(node);
        return;
      }
    }
    setSelectedNode(null);
  };

  if (loading) return <Loading />;

  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="text-center py-20 animate-fade-in">
        <div className="text-6xl mb-5 animate-float">🕸️</div>
        <h2 className="text-xl font-bold text-gray-800 mb-2">暂无知识图谱</h2>
        <p className="text-sm text-gray-400">完成学习和复习后，知识图谱将自动生成</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col animate-fade-in">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-bold text-gray-800">知识图谱</h1>
          <p className="text-xs text-gray-400 mt-0.5">
            {graph.nodes.length} 个节点 · {graph.edges.length} 条关系 · 力导向布局
          </p>
        </div>
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
          {FILTER_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setFilter(opt.value)}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                filter === opt.value
                  ? 'bg-white text-gray-800 shadow-sm'
                  : 'text-gray-400 hover:text-gray-600'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 flex gap-4">
        <div className="flex-1 bg-white rounded-2xl border border-gray-100 overflow-hidden shadow-sm">
          <canvas
            ref={canvasRef}
            className="w-full h-full cursor-grab active:cursor-grabbing"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            onWheel={handleWheel}
            onClick={handleClick}
          />
        </div>

        {/* 图例 */}
        <div className="w-48 space-y-3">
          <Card>
            <h3 className="text-xs font-semibold text-gray-500 mb-2">图例</h3>
            <div className="space-y-1.5 text-xs">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full" style={{ background: '#10B981' }} />
                <span className="text-gray-600">章节</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full" style={{ background: '#8B5CF6' }} />
                <span className="text-gray-600">知识单元</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full" style={{ background: '#3B82F6' }} />
                <span className="text-gray-600">概念</span>
              </div>
            </div>
          </Card>
          <Card>
            <h3 className="text-xs font-semibold text-gray-500 mb-2">关系</h3>
            <div className="space-y-1.5 text-xs">
              <div className="flex items-center gap-2">
                <span className="w-6 border-t-2 border-gray-300" />
                <span className="text-gray-600">关联</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-6 border-t-2 border-dashed" style={{ borderColor: '#93C5FD' }} />
                <span className="text-gray-600">相似</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-6 border-t-2" style={{ borderColor: '#F59E0B' }} />
                <span className="text-gray-600">依赖 →</span>
              </div>
            </div>
          </Card>
        </div>

        {/* 节点详情 */}
        {selectedNode && (
          <div className="w-64 animate-slide-right">
            <Card>
              <div className="flex items-center gap-3 mb-4">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center text-white text-sm font-bold"
                  style={{
                    background:
                      selectedNode.color ||
                      NODE_COLORS[selectedNode.node_type] ||
                      '#6B7280',
                  }}
                >
                  {selectedNode.label.charAt(0)}
                </div>
                <div>
                  <h3 className="font-semibold text-gray-800 text-sm">
                    {selectedNode.label}
                  </h3>
                  <p className="text-[10px] text-gray-400 uppercase">
                    {selectedNode.node_type}
                  </p>
                </div>
              </div>
              {selectedNode.mastery_score !== undefined && (
                <div className="pt-3 border-t border-gray-100">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs text-gray-400">掌握度</span>
                    <span className="text-xs font-semibold text-gray-600">
                      {Math.round(selectedNode.mastery_score * 100)}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div
                      className="h-2 rounded-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all"
                      style={{ width: `${selectedNode.mastery_score * 100}%` }}
                    />
                  </div>
                </div>
              )}
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
