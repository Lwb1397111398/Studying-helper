// Settings API

import client from './client';
import type { UserSettings, AIConfigResponse } from '../types';

// 获取用户偏好
export const getPreferences = (): Promise<UserSettings> => {
  return client.get('/settings/preferences');
};

// 更新用户偏好
export const updatePreferences = (settings: Partial<UserSettings>): Promise<UserSettings> => {
  return client.put('/settings/preferences', settings);
};

// 获取 AI 配置（只读）
export const getAIConfig = (): Promise<AIConfigResponse> => {
  return client.get('/settings/ai-config');
};
