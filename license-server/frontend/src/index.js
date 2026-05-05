import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "sonner";
import App from "./App";
import { captureReferralFromUrl } from "./lib/referral";
import "./index.css";

captureReferralFromUrl();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
      <Toaster theme="dark" position="top-right" richColors />
    </BrowserRouter>
  </React.StrictMode>
);
