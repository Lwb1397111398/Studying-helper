import axios from 'axios';

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：自动带 token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器
client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    // 401 时清除 token，引导重新登录
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
    }
    const message = error.response?.data?.detail || error.message || '请求失败';
    return Promise.reject(new Error(message));
  }
);

export default client;
