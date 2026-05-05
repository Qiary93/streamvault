import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL || "";

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

// Auto-refresh access token on 401.
let refreshing = null;
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retried && !original.url.endsWith("/api/auth/refresh")) {
      original._retried = true;
      try {
        refreshing = refreshing || api.post("/api/auth/refresh");
        await refreshing;
        refreshing = null;
        return api(original);
      } catch {
        refreshing = null;
      }
    }
    return Promise.reject(error);
  }
);

export const auth = {
  register: (data) => api.post("/api/auth/register", data),
  login: (data) => api.post("/api/auth/login", data),
  logout: () => api.post("/api/auth/logout"),
  me: () => api.get("/api/auth/me"),
};

export const products = {
  list: () => api.get("/api/products"),
  get: (id) => api.get(`/api/products/${id}`),
};

export const checkout = {
  create: (productId) =>
    api.post("/api/checkout/create", {
      product_id: productId,
      origin_url: window.location.origin,
    }),
  status: (sessionId) => api.get(`/api/checkout/status/${sessionId}`),
};

export const licenses = {
  list: () => api.get("/api/licenses"),
  changeIp: (licenseId, newIp) =>
    api.post("/api/licenses/change-ip", { license_id: licenseId, new_ip: newIp }),
};
