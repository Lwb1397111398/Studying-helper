// Settings API

import client from './client';
import type { UserSettings, AIConfigResponse, AIConfigUpdate } from '../types';

// 获取用户偏好
export const getPreferences = (): Promise<UserSettings> => {
  return client.get('/v1/settings/preferences');
};

// 更新用户偏好
export const updatePreferences = (settings: Partial<UserSettings>): Promise<UserSettings> => {
  return client.put('/v1/settings/preferences', settings);
};

// 获取 AI 配置
export const getAIConfig = (): Promise<AIConfigResponse> => {
  return client.get('/v1/settings/ai-config');
};

// 更新 AI 配置
export const updateAIConfig = (config: AIConfigUpdate): Promise<AIConfigResponse> => {
  return client.put('/v1/settings/ai-config', config);
};
