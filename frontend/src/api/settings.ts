// Settings API

import client from './client';
import type { UserSettings } from '../types';

// 获取用户设置
export const getSettings = (): Promise<Partial<UserSettings>> => {
  return client.get('/settings');
};

// 更新用户设置
export const updateSettings = (settings: Partial<UserSettings>): Promise<UserSettings> => {
  return client.put('/settings', settings);
};
