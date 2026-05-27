// Global app state - auth + user info + settings cache

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type { AuthUser, UserSettings, AIConfigResponse } from '../types';
import { getPreferences, updatePreferences as apiUpdatePreferences, getAIConfig } from '../api/settings';
import client from '../api/client';

interface AppState {
  userId: string;
  user: AuthUser | null;
  isLoggedIn: boolean;
  settings: UserSettings | null;
  settingsLoaded: boolean;
  aiConfig: AIConfigResponse | null;
  login: (username: string) => Promise<void>;
  logout: () => void;
  refreshSettings: () => Promise<void>;
  saveSettings: (patch: Partial<UserSettings>) => Promise<void>;
  refreshAIConfig: () => Promise<void>;
}

const defaultSettings: UserSettings = {
  daily_goal_minutes: 30,
  daily_goal_units: 5,
  review_reminder: true,
  reminder_time: '20:00',
};

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    const saved = localStorage.getItem('user');
    return saved ? JSON.parse(saved) : null;
  });
  const [userId, setUserId] = useState<string>(() =>
    localStorage.getItem('auth_token') ? (user?.id || '') : 'anonymous'
  );
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [aiConfig, setAiConfig] = useState<AIConfigResponse | null>(null);

  const isLoggedIn = !!localStorage.getItem('auth_token');

  const login = useCallback(async (username: string) => {
    const res: any = await client.post('/v1/auth/login', { username });
    localStorage.setItem('auth_token', res.token);
    localStorage.setItem('user', JSON.stringify(res.user));
    setUser(res.user);
    setUserId(res.user.id);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user');
    setUser(null);
    setUserId('anonymous');
  }, []);

  const refreshSettings = useCallback(async () => {
    try {
      const data = await getPreferences();
      setSettings(prev => ({ ...defaultSettings, ...prev, ...data }));
    } catch {
      setSettings(prev => prev ?? defaultSettings);
    } finally {
      setSettingsLoaded(true);
    }
  }, []);

  const saveSettings = useCallback(async (patch: Partial<UserSettings>) => {
    const updated = await apiUpdatePreferences(patch);
    setSettings(prev => ({ ...defaultSettings, ...prev, ...updated }));
  }, []);

  const refreshAIConfig = useCallback(async () => {
    try {
      const data = await getAIConfig();
      setAiConfig(data);
    } catch {
      // 静默失败，AI 配置非关键
    }
  }, []);

  useEffect(() => {
    refreshSettings();
    refreshAIConfig();
  }, [refreshSettings, refreshAIConfig]);

  return (
    <AppContext.Provider value={{
      userId, user, isLoggedIn, settings, settingsLoaded,
      aiConfig,
      login, logout, refreshSettings, saveSettings,
      refreshAIConfig,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useAppState(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useAppState must be used within <AppProvider>');
  return ctx;
}

export { defaultSettings };
