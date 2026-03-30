import axios from 'axios';

const api = axios.create({
    baseURL: 'http://localhost:5000/api',
    headers: { 'Content-Type': 'application/json' },
    withCredentials: true, // Enable sending cookies with requests
});

// Global 401 handler — redirect to login
api.interceptors.response.use(
    (res) => res,
    (err) => {
        if (err.response?.status === 401) {
            window.location.href = '/login';
        }
        return Promise.reject(err);
    }
);

export default api;