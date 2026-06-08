import { useEffect, useRef, useState } from 'react';
import { getKnowledgeGraph } from '../api/knowledgeGraph';
import type { KGNode, KGEdge } from '../types';

interface KnowledgeGraphMiniProps {
  bookId: string;
  highlightUnitId?: string;
  showRelated?: boolean;
}

export default function KnowledgeGraphMini({
  bookId,
  highlightUnitId,
  showRelated = true,
}: KnowledgeGraphMiniProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [nodes, setNodes] = useState<KGNode[]>([]);
  const [edges, setEdges] = useState<KGEdge[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadGraph();
  }, [bookId]);

  useEffect(() => {
    if (nodes.length > 0) {
      drawGraph();
    }
  }, [nodes, edges, highlightUnitId]);

  const loadGraph = async () => {
    try {
      const data = await getKnowledgeGraph(bookId);
      let graphNodes = data.nodes;
      let graphEdges = data.edges;

      // 如果指定了高亮单元，只显示相关节点
      if (highlightUnitId && showRelated) {
        const relatedIds = new Set<string>();
        relatedIds.add(highlightUnitId);

        // 找出相关的边
        for (const edge of graphEdges) {
          if (edge.source_id === highlightUnitId) {
            relatedIds.add(edge.target_id);
          }
          if (edge.target_id === highlightUnitId) {
            relatedIds.add(edge.source_id);
          }
        }

        graphNodes = graphNodes.filter((n) => relatedIds.has(n.id));
        graphEdges = graphEdges.filter(
          (e) => relatedIds.has(e.source_id) && relatedIds.has(e.target_id),
        );
      }

      setNodes(graphNodes);
      setEdges(graphEdges);
    } catch (error) {
      console.error('加载知识图谱失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const drawGraph = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 设置高 DPI 画布
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;
    const centerX = width / 2;
    const centerY = height / 2;

    // 节点位置（圆形布局）
    const nodePositions = new Map<string, { x: number; y: number }>();
    const angleStep = (2 * Math.PI) / nodes.length;

    nodes.forEach((node, i) => {
      const angle = i * angleStep - Math.PI / 2;
      const radius = Math.min(width, height) * 0.35;
      nodePositions.set(node.id, {
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * radius,
      });
    });

    // 清空画布
    ctx.clearRect(0, 0, width, height);

    // 绘制边
    for (const edge of edges) {
      const source = nodePositions.get(edge.source_id);
      const target = nodePositions.get(edge.target_id);
      if (!source || !target) continue;

      ctx.beginPath();
      ctx.moveTo(source.x, source.y);
      ctx.lineTo(target.x, target.y);
      ctx.strokeStyle =
        edge.relation_type === 'depends_on' ? '#6366f1' : '#d1d5db';
      ctx.lineWidth = edge.relation_type === 'depends_on' ? 2 : 1;
      ctx.stroke();
    }

    // 绘制节点
    for (const node of nodes) {
      const pos = nodePositions.get(node.id);
      if (!pos) continue;

      const isHighlighted = node.id === highlightUnitId;
      const radius = isHighlighted ? 18 : 10;

      // 节点圆圈
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = isHighlighted ? '#3b82f6' : node.color || '#9ca3af';
      ctx.fill();

      if (isHighlighted) {
        ctx.strokeStyle = '#1d4ed8';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // 节点标签
      ctx.fillStyle = '#374151';
      ctx.font = isHighlighted ? 'bold 11px sans-serif' : '10px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const label = node.short_label || node.label;
      ctx.fillText(label, pos.x, pos.y + radius + 4);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48 bg-gray-50 rounded-xl">
        <span className="text-sm text-gray-400">加载图谱中...</span>
      </div>
    );
  }

  if (nodes.length === 0) {
    return null;
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-4">
      <h4 className="text-sm font-semibold text-gray-700 mb-2">知识图谱</h4>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: '200px' }}
        className="rounded-lg"
      />
      <div className="flex gap-4 mt-2 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-blue-500"></span> 当前单元
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-gray-300"></span> 相关单元
        </span>
      </div>
    </div>
  );
}
