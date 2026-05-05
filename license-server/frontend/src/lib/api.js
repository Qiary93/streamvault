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
  create: (productId, couponCode, referralCode) =>
    api.post("/api/checkout/create", {
      product_id: productId,
      origin_url: window.location.origin,
      coupon_code: couponCode || undefined,
      referral_code: referralCode || undefined,
    }),
  status: (sessionId) => api.get(`/api/checkout/status/${sessionId}`),
};

export const licenses = {
  list: () => api.get("/api/licenses"),
  changeIp: (licenseId, newIp) =>
    api.post("/api/licenses/change-ip", { license_id: licenseId, new_ip: newIp }),
};

export const coupons = {
  validate: (code, productId) =>
    api.post("/api/coupons/validate", { code, product_id: productId }),
  // admin
  list: () => api.get("/api/coupons"),
  create: (data) => api.post("/api/coupons", data),
  update: (code, data) => api.put(`/api/coupons/${code}`, data),
  delete: (code) => api.delete(`/api/coupons/${code}`),
};

export const affiliates = {
  me: () => api.get("/api/affiliates/me"),
  signup: (code) => api.post("/api/affiliates/signup", { code }),
  mySales: () => api.get("/api/affiliates/me/sales"),
  // admin
  list: () => api.get("/api/affiliates"),
  markPaid: (userId) => api.post(`/api/affiliates/${userId}/mark-paid`),
};

export const admin = {
  stats: () => api.get("/api/admin/stats"),
  users: (q) => api.get(`/api/admin/users${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  licenses: (status, q) => {
    const p = new URLSearchParams();
    if (status) p.set("status", status);
    if (q) p.set("q", q);
    return api.get(`/api/admin/licenses?${p.toString()}`);
  },
  revoke: (licenseId, reason) =>
    api.post(`/api/admin/licenses/${licenseId}/revoke`, { reason }),
  refund: (licenseId, reason, revoke) =>
    api.post(`/api/admin/licenses/${licenseId}/refund`, { reason, revoke_license: revoke }),
  manualIssue: (data) => api.post("/api/admin/licenses/manual", data),
};
