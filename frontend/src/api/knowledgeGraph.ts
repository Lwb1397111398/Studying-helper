import client from './client';
import type { KnowledgeGraph, KGNode } from '../types';

// 获取书籍的知识图谱
export const getKnowledgeGraph = (bookId: string): Promise<KnowledgeGraph> => {
  return client.get(`/v1/knowledge-graph/${bookId}`);
};

// 获取节点详情
export const getNodeDetail = (nodeId: string): Promise<KGNode & { related_units: string[] }> => {
  return client.get(`/v1/knowledge-graph/nodes/${nodeId}`);
};

// 按类型筛选节点
export const getNodesByType = (bookId: string, nodeType: string): Promise<KGNode[]> => {
  return client.get(`/v1/knowledge-graph/${bookId}/nodes`, { params: { type: nodeType } });
};
