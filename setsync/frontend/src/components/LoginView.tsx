import React from "react";
import { Database, Sparkles } from "lucide-react";

interface LoginViewProps {
  loginMode: "user" | "register" | "token";
  setLoginMode: (mode: "user" | "register" | "token") => void;
  loginEmail: string;
  setLoginEmail: (val: string) => void;
  loginPassword: string;
  setLoginPassword: (val: string) => void;
  regOrgName: string;
  setRegOrgName: (val: string) => void;
  regEmail: string;
  setRegEmail: (val: string) => void;
  regPassword: string;
  setRegPassword: (val: string) => void;
  tokenInput: string;
  setTokenInput: (val: string) => void;
  loginError: string;
  setLoginError: (val: string) => void;
  loggingIn: boolean;
  handleUserLogin: (e: React.FormEvent) => void;
  handleRegister: (e: React.FormEvent) => void;
  handleMasterTokenLogin: (e: React.FormEvent) => void;
  setShowPromoAd: (val: boolean) => void;
}

export default function LoginView({
  loginMode,
  setLoginMode,
  loginEmail,
  setLoginEmail,
  loginPassword,
  setLoginPassword,
  regOrgName,
  setRegOrgName,
  regEmail,
  setRegEmail,
  regPassword,
  setRegPassword,
  tokenInput,
  setTokenInput,
  loginError,
  setLoginError,
  loggingIn,
  handleUserLogin,
  handleRegister,
  handleMasterTokenLogin,
  setShowPromoAd
}: LoginViewProps) {
  return (
    <div className="modal-overlay" style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh" }}>
      <div className="modal-content" style={{ maxWidth: "460px", width: "100%", margin: "0 1.5rem", borderRadius: "16px", padding: "2.5rem" }}>
        <div className="modal-header" style={{ marginBottom: "1.5rem", borderBottom: "none", textAlign: "center", justifyContent: "center" }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.5rem" }}>
            <Database size={48} style={{ color: "var(--accent-cyan)" }} />
            <h2 style={{ fontSize: "1.75rem", fontWeight: "700", color: "var(--text-primary)" }}>SetSync Enterprise</h2>
            <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Multi-Tenant Orchestration Platform</span>
          </div>
        </div>
        
        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.75rem" }}>
          <button 
            type="button"
            className={`btn btn-sm ${loginMode === "user" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => { setLoginMode("user"); setLoginError(""); }}
            style={{ flex: 1 }}
          >
            User Login
          </button>
          <button 
            type="button"
            className={`btn btn-sm ${loginMode === "register" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => { setLoginMode("register"); setLoginError(""); }}
            style={{ flex: 1 }}
          >
            Register Org
          </button>
          <button 
            type="button"
            className={`btn btn-sm ${loginMode === "token" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => { setLoginMode("token"); setLoginError(""); }}
            style={{ flex: 1 }}
          >
            API Token
          </button>
        </div>

        {loginMode === "user" && (
          <form onSubmit={handleUserLogin} className="modal-body" style={{ gap: "1rem", padding: 0, display: "flex", flexDirection: "column" }}>
            <input
              type="email"
              className="search-input"
              style={{ paddingLeft: "1rem", height: "44px", borderRadius: "8px", width: "100%" }}
              placeholder="Email address"
              value={loginEmail}
              onChange={(e) => setLoginEmail(e.target.value)}
            />
            <input
              type="password"
              className="search-input"
              style={{ paddingLeft: "1rem", height: "44px", borderRadius: "8px", width: "100%" }}
              placeholder="Password"
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
            />
            {loginError && <p style={{ color: "var(--danger)", fontSize: "0.85rem", margin: 0 }}>{loginError}</p>}
            <button 
              type="submit" 
              className="btn btn-primary" 
              style={{ width: "100%", height: "44px", borderRadius: "8px", fontWeight: "600", marginTop: "0.5rem" }}
              disabled={loggingIn}
            >
              {loggingIn ? "Signing In..." : "Sign In"}
            </button>
          </form>
        )}

        {loginMode === "register" && (
          <form onSubmit={handleRegister} className="modal-body" style={{ gap: "1rem", padding: 0, display: "flex", flexDirection: "column" }}>
            <input
              type="text"
              className="search-input"
              style={{ paddingLeft: "1rem", height: "44px", borderRadius: "8px", width: "100%" }}
              placeholder="Organization Name (e.g. Acme Corp)"
              value={regOrgName}
              onChange={(e) => setRegOrgName(e.target.value)}
            />
            <input
              type="email"
              className="search-input"
              style={{ paddingLeft: "1rem", height: "44px", borderRadius: "8px", width: "100%" }}
              placeholder="Admin Email"
              value={regEmail}
              onChange={(e) => setRegEmail(e.target.value)}
            />
            <input
              type="password"
              className="search-input"
              style={{ paddingLeft: "1rem", height: "44px", borderRadius: "8px", width: "100%" }}
              placeholder="Admin Password"
              value={regPassword}
              onChange={(e) => setRegPassword(e.target.value)}
            />
            {loginError && <p style={{ color: "var(--danger)", fontSize: "0.85rem", margin: 0 }}>{loginError}</p>}
            <button 
              type="submit" 
              className="btn btn-primary" 
              style={{ width: "100%", height: "44px", borderRadius: "8px", fontWeight: "600", marginTop: "0.5rem" }}
              disabled={loggingIn}
            >
              {loggingIn ? "Creating Account..." : "Create Organization & Admin"}
            </button>
          </form>
        )}

        {loginMode === "token" && (
          <form onSubmit={handleMasterTokenLogin} className="modal-body" style={{ gap: "1rem", padding: 0, display: "flex", flexDirection: "column" }}>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: 0 }}>
              Unlock local instance using the system master API security token.
            </p>
            <input
              type="password"
              className="search-input"
              style={{ paddingLeft: "1rem", height: "44px", borderRadius: "8px", width: "100%" }}
              placeholder="Master API Token..."
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
            />
            {loginError && <p style={{ color: "var(--danger)", fontSize: "0.85rem", margin: 0 }}>{loginError}</p>}
            <button 
              type="submit" 
              className="btn btn-primary" 
              style={{ width: "100%", height: "44px", borderRadius: "8px", fontWeight: "600", marginTop: "0.5rem" }}
              disabled={loggingIn}
            >
              {loggingIn ? "Connecting..." : "Verify & Connect"}
            </button>
          </form>
        )}

        <div style={{ marginTop: "1.5rem", textAlign: "center", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "1rem" }}>
          <button
            onClick={() => setShowPromoAd(true)}
            className="btn btn-secondary"
            style={{ width: "100%", height: "44px", borderRadius: "8px", fontWeight: "600", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem", background: "rgba(0, 242, 254, 0.05)", border: "1px solid rgba(0, 242, 254, 0.2)", color: "var(--accent-cyan)" }}
          >
            <Sparkles size={16} /> Watch Cinematic Promo Ad
          </button>
        </div>
      </div>
    </div>
  );
}
