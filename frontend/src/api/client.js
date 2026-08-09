import axios from 'axios';

export const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  timeout: 30000,
});

apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('x_session_token');
    if (token) {
      config.headers['X-Session-Token'] = token;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);
