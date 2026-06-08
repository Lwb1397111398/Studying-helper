import client from './client';
import type { KnowledgeGraph, KGNode, KGEdge, VisualizationData } from '../types';

// 获取书籍的知识图谱
export const getKnowledgeGraph = (bookId: string): Promise<KnowledgeGraph> => {
  return client.get(`/v1/knowledge-graph/${bookId}`);
};

// 获取可视化数据（支持中心节点、节点数限制）
export const getVisualizationData = (
  bookId: string,
  params?: { center_node_id?: string; max_nodes?: number },
): Promise<VisualizationData> => {
  return client.get(`/v1/knowledge-graph/${bookId}/visualization`, { params });
};

// 查询节点邻居
export const getNodeNeighbors = (
  bookId: string,
  nodeId: string,
  params?: { node_types?: string[]; relation_types?: string[]; min_weight?: number; max_depth?: number },
): Promise<{ nodes: KGNode[]; edges: KGEdge[] }> => {
  return client.get(`/v1/knowledge-graph/${bookId}/neighbors/${nodeId}`, { params });
};

// 查找两节点间路径
export const findPath = (
  bookId: string,
  sourceId: string,
  targetId: string,
): Promise<{ found: boolean; path: KGEdge[] }> => {
  return client.get(`/v1/knowledge-graph/${bookId}/path`, {
    params: { source_id: sourceId, target_id: targetId },
  });
};

// 手动添加边
export const addEdge = (
  bookId: string,
  edge: { source_id: string; target_id: string; relation_type: string; weight?: number },
): Promise<KGEdge> => {
  return client.post(`/v1/knowledge-graph/${bookId}/edges`, edge);
};

// 删除边
export const removeEdge = (bookId: string, edgeId: string): Promise<void> => {
  return client.delete(`/v1/knowledge-graph/${bookId}/edges/${edgeId}`);
};

// 增量更新图谱（学完一个单元后）
export const updateUnitGraph = (
  bookId: string,
  unitId: string,
  data: {
    title: string;
    concepts?: string[];
    prerequisites?: string[];
    summary?: string;
    key_points?: string[];
    difficulty_level?: number;
    importance_score?: number;
  },
): Promise<KnowledgeGraph> => {
  return client.post(`/v1/knowledge-graph/${bookId}/units/${unitId}`, { ...data, unit_id: unitId });
};
