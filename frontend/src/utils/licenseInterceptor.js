// Side-effect module — installs a global axios response interceptor that
// detects `503 + code: "UNLICENSED"` from the backend and dispatches a
// `streamvault:unlicensed` window event. The UnlicensedOverlay component
// listens for that event and renders a fullscreen lockout.
import axios from "axios";

axios.interceptors.response.use(
  (r) => r,
  (error) => {
    const data = error?.response?.data;
    if (
      error?.response?.status === 503 &&
      data &&
      typeof data === "object" &&
      data.code === "UNLICENSED"
    ) {
      try {
        window.dispatchEvent(
          new CustomEvent("streamvault:unlicensed", { detail: data })
        );
      } catch {
        /* ignore */
      }
    }
    return Promise.reject(error);
  }
);

export default true;
