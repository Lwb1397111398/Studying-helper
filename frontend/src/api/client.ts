import axios from 'axios';

const client = axios.create({
  baseURL: '/api',
  timeout: 30000, // 默认 30 秒，AI 学习等长耗时端点需单独覆盖
  headers: {
    'Content-Type': 'application/json',
  },
});

// FormData 请求交给浏览器自动设置 multipart boundary
client.interceptors.request.use((config) => {
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type'];
  }
  return config;
});

// 响应拦截器
client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败';
    return Promise.reject(new Error(message));
  }
);

export default client;
