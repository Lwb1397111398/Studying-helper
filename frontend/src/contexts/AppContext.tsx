// Global app state - settings cache (单机模式，无需登录)

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type { UserSettings, AIConfigResponse, AIConfigUpdate } from '../types';
import { getPreferences, updatePreferences as apiUpdatePreferences, getAIConfig, updateAIConfig } from '../api/settings';

interface AppState {
  userId: string;
  settings: UserSettings | null;
  settingsLoaded: boolean;
  aiConfig: AIConfigResponse | null;
  refreshSettings: () => Promise<void>;
  saveSettings: (patch: Partial<UserSettings>) => Promise<void>;
  refreshAIConfig: () => Promise<void>;
  saveAIConfig: (config: AIConfigUpdate) => Promise<void>;
}

const defaultSettings: UserSettings = {
  daily_goal_minutes: 30,
  daily_goal_units: 5,
  review_reminder: true,
  reminder_time: '20:00',
  llm_max_concurrent: 3,
};

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [aiConfig, setAiConfig] = useState<AIConfigResponse | null>(null);

  const refreshSettings = useCallback(async () => {
    try {
      const data = await getPreferences();
      setSettings(prev => ({ ...defaultSettings, ...(prev ?? {}), ...data }));
    } catch {
      setSettings(prev => prev ?? defaultSettings);
    } finally {
      setSettingsLoaded(true);
    }
  }, []);

  const saveSettings = useCallback(async (patch: Partial<UserSettings>) => {
    const updated = await apiUpdatePreferences(patch);
    setSettings(prev => ({ ...defaultSettings, ...(prev ?? {}), ...updated }));
  }, []);

  const refreshAIConfig = useCallback(async () => {
    try {
      const data = await getAIConfig();
      setAiConfig(data);
    } catch {
      // 静默失败，AI 配置非关键
    }
  }, []);

  const saveAIConfig = useCallback(async (config: AIConfigUpdate) => {
    const updated = await updateAIConfig(config);
    setAiConfig(updated);
  }, []);

  useEffect(() => {
    refreshSettings();
    refreshAIConfig();
  }, []);

  return (
    <AppContext.Provider value={{
      userId: 'anonymous', settings, settingsLoaded,
      aiConfig,
      refreshSettings, saveSettings,
      refreshAIConfig, saveAIConfig,
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
