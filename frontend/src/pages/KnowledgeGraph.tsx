import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import Card from '../components/Card';
import Loading from '../components/Loading';
import { getKnowledgeGraph, getNodeNeighbors, findPath } from '../api/knowledgeGraph';
import type { KnowledgeGraph as KGType, KGNode, KGEdge } from '../types';

const NODE_COLORS: Record<string, string> = {
  concept: '#4F8EF7',
  chapter: '#34D399',
  knowledge_unit: '#A78BFA',
};

const NODE_COLORS_LIGHT: Record<string, string> = {
  concept: '#93B8FD',
  chapter: '#86EFAC',
  knowledge_unit: '#C4B5FD',
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
  label: string;       // 短标签（节点上显示）
  fullLabel: string;    // 完整标签（悬停/详情显示）
  node_type: string;
  mastery_score?: number;
}

interface SimEdge {
  id: string;
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
) {
  const nodeMap = new Map<string, SimNode>();
  nodes.forEach((n) => nodeMap.set(n.id, n));

  const cx = width / 2;
  const cy = height / 2;
  nodes.forEach((n, index) => {
    if (n.x === 0 && n.y === 0) {
      const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2;
      const radius = 120 + (index % 5) * 35;
      n.x = cx + Math.cos(angle) * radius;
      n.y = cy + Math.sin(angle) * radius;
    }
  });

  const density = Math.max(1, nodes.length / 35);
  const repulsion = 9000 * density;
  const attraction = 0.0026 / Math.sqrt(density);
  const damping = 0.82;
  const idealLen = Math.max(110, Math.min(230, 230 - nodes.length * 1.5));
  const iterations = Math.max(360, Math.min(760, 320 + nodes.length * 6));

  for (let iter = 0; iter < iterations; iter++) {
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const minDist = (a.size + b.size) / 2 + 24;
        const collisionForce = dist < minDist ? (minDist - dist) * 0.7 : 0;
        const force = collisionForce + repulsion / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        a.vx -= fx;
        a.vy -= fy;
        b.vx += fx;
        b.vy += fy;
      }
    }

    for (const edge of edges) {
      const a = nodeMap.get(edge.source);
      const b = nodeMap.get(edge.target);
      if (!a || !b) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const relationFactor = edge.relation_type === 'part_of' ? 2.8 : edge.relation_type === 'depends_on' ? 1.35 : 0.75;
      const edgeLen = edge.relation_type === 'part_of' ? idealLen * 0.62 : idealLen;
      const force = (dist - edgeLen) * attraction * relationFactor * Math.max(0.5, edge.weight || 1);
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      a.vx += fx;
      a.vy += fy;
      b.vx -= fx;
      b.vy -= fy;
    }

    for (const edge of edges) {
      if (edge.relation_type !== 'part_of') continue;
      const parent = nodeMap.get(edge.target)?.node_type === 'chapter' ? nodeMap.get(edge.target) : nodeMap.get(edge.source);
      const child = parent?.id === edge.source ? nodeMap.get(edge.target) : nodeMap.get(edge.source);
      if (!parent || !child || child.node_type === 'chapter') continue;
      child.vx += (parent.x - child.x) * 0.0016;
      child.vy += (parent.y - child.y) * 0.0016;
    }

    for (const n of nodes) {
      const centerFactor = n.node_type === 'chapter' ? 0.0006 : 0.00025;
      n.vx += (cx - n.x) * centerFactor;
      n.vy += (cy - n.y) * centerFactor;
    }

    const margin = 100;
    for (const n of nodes) {
      n.vx *= damping;
      n.vy *= damping;
      n.x += n.vx;
      n.y += n.vy;
      n.x = Math.max(margin, Math.min(width - margin, n.x));
      n.y = Math.max(margin, Math.min(height - margin, n.y));
    }
  }
}

// 标签防重叠：碰撞检测 + 迭代推开
interface LabelPlacement {
  x: number;
  y: number;
  w: number;
  h: number;
  needsConnector: boolean;
}

function resolveLabelOverlaps(
  nodes: { x: number; y: number; label: string; size: number; node_type: string }[],
  ctx: CanvasRenderingContext2D,
  maxIter: number = 28,
): LabelPlacement[] {
  const GAP = 6;
  const MAX_OFFSET = 86;

  ctx.font = '600 12px Inter, Noto Sans SC, sans-serif';
  const labels = nodes
    .map((n, index) => {
      const w = ctx.measureText(n.label).width + 16;
      const h = 22;
      const nodeR = n.size / 2;
      return {
        index,
        nodeX: n.x,
        nodeY: n.y,
        priority: n.node_type === 'chapter' ? 3 : n.node_type === 'knowledge_unit' ? 2 : 1,
        w,
        h,
        nx: n.x,
        ny: n.y + nodeR + 16,
      };
    })
    .sort((a, b) => b.priority - a.priority || b.w - a.w);

  for (let iter = 0; iter < maxIter; iter++) {
    let moved = false;
    for (let i = 0; i < labels.length; i++) {
      for (let j = i + 1; j < labels.length; j++) {
        const a = labels[i];
        const b = labels[j];
        const overlapX = (a.w + b.w) / 2 + GAP - Math.abs(a.nx - b.nx);
        const overlapY = (a.h + b.h) / 2 + GAP - Math.abs(a.ny - b.ny);
        if (overlapX <= 0 || overlapY <= 0) continue;

        const movable = a.priority >= b.priority ? b : a;
        const anchor = movable === a ? b : a;
        const dx = movable.nx - anchor.nx;
        const dy = movable.ny - anchor.ny;
        const preferHorizontal = overlapX < overlapY;
        const dirX = dx === 0 ? (movable.index % 2 === 0 ? 1 : -1) : Math.sign(dx);
        const dirY = dy === 0 ? 1 : Math.sign(dy);

        if (preferHorizontal) {
          movable.nx += (overlapX + GAP) * dirX;
        } else {
          movable.ny += (overlapY + GAP) * dirY;
        }
        moved = true;
      }
    }
    if (!moved) break;
  }

  const placements: LabelPlacement[] = [];
  labels.forEach((l) => {
    let dx = l.nx - l.nodeX;
    let dy = l.ny - l.nodeY;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist > MAX_OFFSET) {
      dx = (dx / dist) * MAX_OFFSET;
      dy = (dy / dist) * MAX_OFFSET;
    }
    placements[l.index] = {
      x: l.nodeX + dx,
      y: l.nodeY + dy,
      w: l.w,
      h: l.h,
      needsConnector: Math.abs(dx) > 10 || Math.abs(dy) > 34,
    };
  });
  return placements;
}

function drawRoundedRectPath(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
}

function drawNodePath(ctx: CanvasRenderingContext2D, node: SimNode, x: number, y: number, scale = 1) {
  const r = (node.size / 2) * scale;
  if (node.node_type === 'chapter') {
    for (let i = 0; i < 6; i++) {
      const angle = Math.PI / 6 + (i * Math.PI) / 3;
      const px = x + Math.cos(angle) * r;
      const py = y + Math.sin(angle) * r;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();
  } else if (node.node_type === 'knowledge_unit') {
    drawRoundedRectPath(ctx, x - r * 1.25, y - r * 0.78, r * 2.5, r * 1.56, Math.min(12, r * 0.45));
  } else {
    ctx.moveTo(x, y - r);
    ctx.lineTo(x + r, y);
    ctx.lineTo(x, y + r);
    ctx.lineTo(x - r, y);
    ctx.closePath();
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
  const [mode, setMode] = useState<'view' | 'path'>('view');
  const [pathStart, setPathStart] = useState<KGNode | null>(null);
  const [pathEnd, setPathEnd] = useState<KGNode | null>(null);
  const [pathEdges, setPathEdges] = useState<KGEdge[]>([]);
  const [neighbors, setNeighbors] = useState<{ nodes: KGNode[]; edges: KGEdge[] } | null>(null);
  const [loadingNeighbors, setLoadingNeighbors] = useState(false);
  const [hoveredNode, setHoveredNode] = useState<{ label: string; x: number; y: number } | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null);

  // 力导向计算后的节点位置
  const simNodesRef = useRef<SimNode[]>([]);
  const simEdgesRef = useRef<SimEdge[]>([]);
  const nodePosMapRef = useRef<Map<string, { x: number; y: number }>>(new Map());

  useEffect(() => {
    if (bookId) loadGraph();
  }, [bookId]);

  // 布局只在 graph 或 filter 变化时计算
  useEffect(() => {
    if (graph) {
      computeLayout();
      drawGraph();
    }
  }, [graph, filter]);

  // transform 变化时只重绘（不重新布局）
  useEffect(() => {
    if (graph) {
      drawGraph();
    }
  }, [transform, selectedNode, neighbors, pathEdges, pathStart, pathEnd, focusedNodeId, searchQuery]);

  const filteredSearchResults = useMemo(() => {
    if (!graph || !searchQuery.trim()) return [];
    const keyword = searchQuery.trim().toLowerCase();
    return graph.nodes
      .filter((node) => filter === 'all' || node.node_type === filter)
      .filter((node) => node.label.toLowerCase().includes(keyword) || node.short_label?.toLowerCase().includes(keyword))
      .slice(0, 8);
  }, [filter, graph, searchQuery]);

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

  const loadNeighbors = async (nodeId: string) => {
    if (!bookId) return;
    setLoadingNeighbors(true);
    try {
      const data = await getNodeNeighbors(bookId, nodeId, { max_depth: 1 });
      setNeighbors(data);
    } catch (error) {
      console.error('加载邻居节点失败:', error);
      setNeighbors(null);
    } finally {
      setLoadingNeighbors(false);
    }
  };

  const handleFindPath = async () => {
    if (!bookId || !pathStart || !pathEnd) return;
    try {
      const result = await findPath(bookId, pathStart.id, pathEnd.id);
      if (result.found) {
        setPathEdges(result.path);
      } else {
        setPathEdges([]);
        alert('未找到路径');
      }
    } catch (error) {
      console.error('查找路径失败:', error);
      setPathEdges([]);
    }
  };

  const clearPath = () => {
    setPathStart(null);
    setPathEnd(null);
    setPathEdges([]);
  };

  const focusNode = (node: KGNode) => {
    const canvas = canvasRef.current;
    const pos = nodePosMapRef.current.get(node.id);
    if (!canvas || !pos) return;
    const nextScale = Math.max(1.25, transform.scale);
    setFocusedNodeId(node.id);
    setSelectedNode(node);
    loadNeighbors(node.id);
    setTransform({
      x: canvas.offsetWidth / 2 - pos.x * nextScale,
      y: canvas.offsetHeight / 2 - pos.y * nextScale,
      scale: nextScale,
    });
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

    const simNodes: SimNode[] = filteredNodes.map((n) => {
      const baseSize = n.node_type === 'chapter' ? 34 : n.node_type === 'knowledge_unit' ? 28 : 22;
      return {
        id: n.id,
        x: nodePosMapRef.current.get(n.id)?.x ?? 0,
        y: nodePosMapRef.current.get(n.id)?.y ?? 0,
        vx: 0,
        vy: 0,
        size: baseSize + n.size * 5,
        color: n.color || NODE_COLORS[n.node_type] || '#6B7280',
        label: n.short_label || n.label,
        fullLabel: n.label,
        node_type: n.node_type,
        mastery_score: n.mastery_score,
      };
    });

    const simEdges: SimEdge[] = filteredEdges.map((e) => ({
      id: e.id,
      source: e.source_id,
      target: e.target_id,
      weight: e.weight,
      relation_type: e.relation_type,
    }));

    runForceLayout(simNodes, simEdges, width, height);

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

    // 画边（贝塞尔曲线）
    const pathEdgeIds = new Set(pathEdges.map((e) => e.id));
    const neighborEdgeIds = new Set(neighbors?.edges.map((e) => e.id) || []);
    const selectedEdgeNodeIds = new Set([selectedNode?.id, focusedNodeId].filter(Boolean));
    const hasActiveNode = selectedEdgeNodeIds.size > 0 || pathEdgeIds.size > 0 || neighborEdgeIds.size > 0;

    simEdgesRef.current.forEach((edge) => {
      const sourcePos = posMap.get(edge.source);
      const targetPos = posMap.get(edge.target);
      if (!sourcePos || !targetPos) return;

      const mx = (sourcePos.x + targetPos.x) / 2;
      const my = (sourcePos.y + targetPos.y) / 2;
      const dx = targetPos.x - sourcePos.x;
      const dy = targetPos.y - sourcePos.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const offset = Math.min(dist * 0.15, 25);
      const cpx = mx + (-dy / (dist || 1)) * offset;
      const cpy = my + (dx / (dist || 1)) * offset;
      const isActiveEdge = pathEdgeIds.has(edge.id) || neighborEdgeIds.has(edge.id) || selectedEdgeNodeIds.has(edge.source) || selectedEdgeNodeIds.has(edge.target);
      const dimmedAlpha = hasActiveNode && !isActiveEdge ? 0.15 : 1;
      const weightWidth = Math.min(3.2, Math.max(0.8, 0.8 + (edge.weight || 1) * 0.8));

      ctx.beginPath();
      ctx.moveTo(sourcePos.x, sourcePos.y);
      ctx.quadraticCurveTo(cpx, cpy, targetPos.x, targetPos.y);

      if (pathEdgeIds.has(edge.id)) {
        ctx.strokeStyle = '#F87171';
        ctx.lineWidth = Math.max(3, weightWidth + 1);
        ctx.globalAlpha = 1;
        ctx.setLineDash([]);
      } else if (neighborEdgeIds.has(edge.id)) {
        ctx.strokeStyle = '#A78BFA';
        ctx.lineWidth = Math.max(2, weightWidth);
        ctx.globalAlpha = 0.92;
        ctx.setLineDash([]);
      } else if (edge.relation_type === 'depends_on') {
        ctx.strokeStyle = '#FBBF24';
        ctx.lineWidth = Math.max(1.6, weightWidth);
        ctx.globalAlpha = 0.72 * dimmedAlpha;
        ctx.setLineDash([]);
      } else if (edge.relation_type === 'similar_to') {
        ctx.strokeStyle = '#93C5FD';
        ctx.lineWidth = Math.max(1.2, weightWidth * 0.75);
        ctx.globalAlpha = 0.42 * dimmedAlpha;
        ctx.setLineDash([6, 4]);
      } else if (edge.relation_type === 'part_of') {
        ctx.strokeStyle = '#6EE7B7';
        ctx.lineWidth = Math.max(1.4, weightWidth * 0.9);
        ctx.globalAlpha = 0.55 * dimmedAlpha;
        ctx.setLineDash([]);
      } else {
        ctx.strokeStyle = '#D1D5DB';
        ctx.lineWidth = weightWidth * 0.7;
        ctx.globalAlpha = 0.3 * dimmedAlpha;
        ctx.setLineDash([]);
      }
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;

      // depends_on 箭头（沿曲线切线方向）
      if (edge.relation_type === 'depends_on') {
        const t = 0.82;
        const arrowX = (1 - t) * (1 - t) * sourcePos.x + 2 * (1 - t) * t * cpx + t * t * targetPos.x;
        const arrowY = (1 - t) * (1 - t) * sourcePos.y + 2 * (1 - t) * t * cpy + t * t * targetPos.y;
        const tangentX = 2 * (1 - t) * (cpx - sourcePos.x) + 2 * t * (targetPos.x - cpx);
        const tangentY = 2 * (1 - t) * (cpy - sourcePos.y) + 2 * t * (targetPos.y - cpy);
        const angle = Math.atan2(tangentY, tangentX);
        const arrowLen = 9;
        ctx.beginPath();
        ctx.moveTo(arrowX, arrowY);
        ctx.lineTo(arrowX - arrowLen * Math.cos(angle - 0.45), arrowY - arrowLen * Math.sin(angle - 0.45));
        ctx.lineTo(arrowX - arrowLen * Math.cos(angle + 0.45), arrowY - arrowLen * Math.sin(angle + 0.45));
        ctx.closePath();
        ctx.fillStyle = '#FBBF24';
        ctx.fill();
      }
    });

    // 画节点（径向渐变 + 阴影）
    const neighborNodeIds = new Set(neighbors?.nodes.map((n) => n.id) || []);

    simNodesRef.current.forEach((node) => {
      const pos = posMap.get(node.id);
      if (!pos) return;
      const r = node.size / 2;
      const lightColor = NODE_COLORS_LIGHT[node.node_type] || '#D1D5DB';
      const isSelected = selectedNode?.id === node.id;
      const isPathNode = pathStart?.id === node.id || pathEnd?.id === node.id;
      const isNeighbor = neighborNodeIds.has(node.id);
      const isSearchMatch = Boolean(searchQuery.trim()) && (node.id === focusedNodeId || node.fullLabel.toLowerCase().includes(searchQuery.trim().toLowerCase()));
      const nodeScale = isSelected || node.id === focusedNodeId ? 1.15 : 1;

      // 阴影
      ctx.save();
      if (isPathNode) {
        ctx.shadowColor = 'rgba(239, 68, 68, 0.5)';
        ctx.shadowBlur = 18;
      } else if (isSelected) {
        ctx.shadowColor = `${node.color}88`;
        ctx.shadowBlur = 16;
      } else if (isNeighbor) {
        ctx.shadowColor = 'rgba(167, 139, 250, 0.4)';
        ctx.shadowBlur = 12;
      } else {
        ctx.shadowColor = `${node.color}44`;
        ctx.shadowBlur = 8;
      }

      // 径向渐变填充
      const grad = ctx.createRadialGradient(pos.x - r * 0.25, pos.y - r * 0.25, r * 0.1, pos.x, pos.y, r);
      grad.addColorStop(0, lightColor);
      grad.addColorStop(0.6, node.color);
      grad.addColorStop(1, node.color);

      ctx.beginPath();
      drawNodePath(ctx, node, pos.x, pos.y, nodeScale);
      ctx.fillStyle = grad;
      ctx.fill();
      ctx.restore();

      ctx.beginPath();
      drawNodePath(ctx, node, pos.x, pos.y, nodeScale);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.92)';
      ctx.lineWidth = 3;
      ctx.stroke();

      // 描边
      if (isPathNode) {
        ctx.beginPath();
        drawNodePath(ctx, node, pos.x, pos.y, nodeScale);
        ctx.strokeStyle = '#EF4444';
        ctx.lineWidth = 3;
        ctx.stroke();
      } else if (isNeighbor) {
        ctx.beginPath();
        drawNodePath(ctx, node, pos.x, pos.y, nodeScale);
        ctx.strokeStyle = '#A78BFA';
        ctx.lineWidth = 2;
        ctx.stroke();
      } else if (isSelected || isSearchMatch) {
        ctx.beginPath();
        drawNodePath(ctx, node, pos.x, pos.y, nodeScale);
        ctx.strokeStyle = isSearchMatch ? '#2563EB' : '#374151';
        ctx.lineWidth = 2.5;
        ctx.stroke();
      }
    });

    // 标签（防重叠 + 背景底色 + 连接线）
    const labelPlacements = resolveLabelOverlaps(simNodesRef.current, ctx);
    simNodesRef.current.forEach((node, i) => {
      const placement = labelPlacements[i];
      const lx = placement.x;
      const ly = placement.y;
      const pos = posMap.get(node.id);
      if (!pos) return;

      ctx.font = '600 12px Inter, Noto Sans SC, sans-serif';

      if (placement.needsConnector) {
        ctx.beginPath();
        ctx.moveTo(pos.x, pos.y + node.size / 2);
        ctx.lineTo(lx, ly - placement.h / 2);
        ctx.strokeStyle = 'rgba(156, 163, 175, 0.35)';
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 2]);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      ctx.fillStyle = 'rgba(255, 255, 255, 0.92)';
      ctx.beginPath();
      drawRoundedRectPath(ctx, lx - placement.w / 2, ly - placement.h / 2, placement.w, placement.h, 5);
      ctx.fill();

      ctx.fillStyle = '#374151';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(node.label, lx, ly);
    });

    ctx.restore();
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - transform.x, y: e.clientY - transform.y });
  };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setTransform((prev) => ({ ...prev, x: e.clientX - dragStart.x, y: e.clientY - dragStart.y }));
      return;
    }
    // 悬停检测
    if (!canvasRef.current || !graph) { setHoveredNode(null); return; }
    const rect = canvasRef.current.getBoundingClientRect();
    const mx = (e.clientX - rect.left - transform.x) / transform.scale;
    const my = (e.clientY - rect.top - transform.y) / transform.scale;
    for (const node of simNodesRef.current) {
      const pos = nodePosMapRef.current.get(node.id);
      if (!pos) continue;
      const r = node.size / 2 + 8;
      if ((mx - pos.x) ** 2 + (my - pos.y) ** 2 <= r * r) {
        setHoveredNode({ label: node.fullLabel, x: e.clientX, y: e.clientY });
        return;
      }
    }
    setHoveredNode(null);
  };
  const handleMouseUp = () => setIsDragging(false);
  const handleWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setTransform((prev) => ({ ...prev, scale: Math.max(0.1, Math.min(5, prev.scale * delta)) }));
  }, []);

  // 注册原生 wheel 事件（passive: false 才能 preventDefault）
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.addEventListener('wheel', handleWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', handleWheel);
  }, [handleWheel]);

  // 全局 mouseup 监听，防止在 canvas 外释放鼠标时 isDragging 未重置
  useEffect(() => {
    const handleGlobalMouseUp = () => setIsDragging(false);
    document.addEventListener('mouseup', handleGlobalMouseUp);
    return () => document.removeEventListener('mouseup', handleGlobalMouseUp);
  }, []);

  const handleClick = (e: React.MouseEvent) => {
    if (!graph || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left - transform.x) / transform.scale;
    const y = (e.clientY - rect.top - transform.y) / transform.scale;

    for (const simNode of simNodesRef.current) {
      const pos = nodePosMapRef.current.get(simNode.id);
      const node = graph.nodes.find((n) => n.id === simNode.id);
      if (!pos || !node) continue;
      const distance = Math.sqrt((x - pos.x) ** 2 + (y - pos.y) ** 2);
      if (distance <= simNode.size / 2 + 8) {
        setFocusedNodeId(null);
        setSelectedNode(node);
        // 加载邻居节点
        loadNeighbors(node.id);
        // 路径模式：选择起点和终点
        if (mode === 'path') {
          if (!pathStart) {
            setPathStart(node);
            setPathEnd(null);
            setPathEdges([]);
          } else if (!pathEnd && node.id !== pathStart.id) {
            setPathEnd(node);
          }
        }
        return;
      }
    }
    setSelectedNode(null);
    setNeighbors(null);
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
        <div className="flex gap-2 items-start">
          {/* 搜索定位 */}
          <div className="relative">
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索节点..."
              className="w-44 px-3 py-2 bg-white border border-gray-100 rounded-xl text-xs text-gray-700 placeholder:text-gray-300 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-100"
            />
            {filteredSearchResults.length > 0 && (
              <div className="absolute right-0 mt-2 w-64 max-h-64 overflow-y-auto bg-white border border-gray-100 rounded-xl shadow-lg z-20 p-1">
                {filteredSearchResults.map((node) => (
                  <button
                    key={node.id}
                    type="button"
                    onClick={() => focusNode(node)}
                    className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-left hover:bg-blue-50 transition-colors"
                  >
                    <span
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ background: NODE_COLORS[node.node_type] || '#6B7280' }}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block text-xs text-gray-700 truncate">{node.label}</span>
                      <span className="block text-[10px] text-gray-400">{node.node_type}</span>
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
          {/* 模式选择 */}
          <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
            <button
              onClick={() => { setMode('view'); clearPath(); }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                mode === 'view' ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-400 hover:text-gray-600'
              }`}
            >
              浏览
            </button>
            <button
              onClick={() => setMode('path')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                mode === 'path' ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-400 hover:text-gray-600'
              }`}
            >
              路径
            </button>
          </div>
          {/* 节点类型筛选 */}
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
      </div>

      <div className="flex-1 flex gap-4">
        <div className="flex-1 bg-white rounded-2xl border border-gray-100 overflow-hidden shadow-sm">
          <canvas
            ref={canvasRef}
            className="w-full h-full cursor-grab active:cursor-grabbing"
            style={{ background: 'radial-gradient(circle, #f0f0f0 1px, transparent 1px)', backgroundSize: '20px 20px' }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={() => { handleMouseUp(); setHoveredNode(null); }}
            onClick={handleClick}
          />
          {/* 悬停 tooltip */}
          {hoveredNode && (
            <div
              className="fixed z-50 px-2.5 py-1.5 bg-gray-900 text-white text-xs rounded-lg shadow-lg pointer-events-none max-w-64"
              style={{ left: hoveredNode.x + 12, top: hoveredNode.y - 30, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
            >
              {hoveredNode.label}
            </div>
          )}
        </div>

        {/* 图例 */}
        <div className="w-48 space-y-3">
          <Card>
            <h3 className="text-xs font-semibold text-gray-500 mb-2">图例</h3>
            <div className="space-y-1.5 text-xs">
              <div className="flex items-center gap-2">
                <span className="w-3.5 h-3.5" style={{ background: '#34D399', clipPath: 'polygon(25% 5%, 75% 5%, 100% 50%, 75% 95%, 25% 95%, 0 50%)' }} />
                <span className="text-gray-600">章节</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-4 h-2.5 rounded" style={{ background: '#A78BFA' }} />
                <span className="text-gray-600">知识单元</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rotate-45" style={{ background: '#4F8EF7' }} />
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
              <div className="flex items-center gap-2">
                <span className="w-6 border-t-2" style={{ borderColor: '#EF4444' }} />
                <span className="text-gray-600">路径</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-6 border-t-2" style={{ borderColor: '#8B5CF6' }} />
                <span className="text-gray-600">关联节点</span>
              </div>
            </div>
          </Card>
        </div>

        {/* 节点详情 */}
        {selectedNode && (
          <div className="w-64 animate-slide-right space-y-3">
            <Card>
              <div className="flex items-center gap-3 mb-4">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center text-white text-sm font-bold flex-shrink-0"
                  style={{
                    background:
                      selectedNode.color ||
                      NODE_COLORS[selectedNode.node_type] ||
                      '#6B7280',
                  }}
                >
                  {selectedNode.label.charAt(0)}
                </div>
                <div className="min-w-0">
                  <h3 className="font-semibold text-gray-800 text-sm break-words">
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

            {/* 路径模式控制 */}
            {mode === 'path' && (
              <Card>
                <h3 className="text-xs font-semibold text-gray-500 mb-2">路径查找</h3>
                <div className="space-y-2 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-red-400" />
                    <span className="text-gray-600">
                      起点: {pathStart ? pathStart.label : '点击选择'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-red-600" />
                    <span className="text-gray-600">
                      终点: {pathEnd ? pathEnd.label : '点击选择'}
                    </span>
                  </div>
                  {pathStart && pathEnd && (
                    <div className="flex gap-2 pt-2">
                      <button
                        onClick={handleFindPath}
                        className="flex-1 px-2 py-1.5 bg-blue-500 text-white rounded-lg text-xs font-medium hover:bg-blue-600 transition-colors"
                      >
                        查找路径
                      </button>
                      <button
                        onClick={clearPath}
                        className="px-2 py-1.5 bg-gray-100 text-gray-600 rounded-lg text-xs font-medium hover:bg-gray-200 transition-colors"
                      >
                        清除
                      </button>
                    </div>
                  )}
                  {pathEdges.length > 0 && (
                    <p className="text-emerald-600 font-medium pt-1">
                      找到路径: {pathEdges.length} 条边
                    </p>
                  )}
                </div>
              </Card>
            )}

            {/* 邻居节点 */}
            {loadingNeighbors ? (
              <Card>
                <p className="text-xs text-gray-400 text-center py-2">加载中...</p>
              </Card>
            ) : neighbors && neighbors.nodes.length > 0 ? (
              <Card>
                <h3 className="text-xs font-semibold text-gray-500 mb-2">
                  关联节点 ({neighbors.nodes.length})
                </h3>
                <div className="space-y-1.5 max-h-48 overflow-y-auto">
                  {neighbors.nodes.slice(0, 10).map((node) => (
                    <div
                      key={node.id}
                      className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                      onClick={() => setSelectedNode(node)}
                    >
                      <div
                        className="w-4 h-4 rounded-full"
                        style={{ background: NODE_COLORS[node.node_type] || '#6B7280' }}
                      />
                      <span className="text-xs text-gray-700 truncate">{node.label}</span>
                      <span className="text-[10px] text-gray-400 ml-auto">{node.node_type}</span>
                    </div>
                  ))}
                </div>
              </Card>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
