import React, { useState, useEffect } from "react";
import { 
  getInventoryStatus, 
  getSetsView, 
  triggerRecompute, 
  dryRunAction, 
  executeCopy, 
  executeMove, 
  undoAction, 
  getAuditLogs,
  testConnection
} from "./api/client";
import type { 
  UnifiedFileRow, 
  SetSummaryStrip, 
  InventoryStatus, 
  ActionResponse, 
  DryRunResponse 
} from "./types";
import { 
  Database, 
  Search, 
  RefreshCw, 
  FolderSync, 
  CheckCircle, 
  AlertTriangle, 
  Undo, 
  History, 
  LayoutDashboard,
  ArrowRight,
  FileCode,
  HardDrive
} from "lucide-react";

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem("setsync_token"));
  const [tokenInput, setTokenInput] = useState("");
  const [loginError, setLoginError] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);

  const [activeTab, setActiveTab] = useState<"dashboard" | "audit">("dashboard");
  const [inventoryStatus, setInventoryStatus] = useState<InventoryStatus | null>(null);
  
  // Set View / Search State
  const [viewType, setViewType] = useState<string>("union");
  const [searchQuery, setSearchQuery] = useState("");
  const [files, setFiles] = useState<UnifiedFileRow[]>([]);
  const [summary, setSummary] = useState<SetSummaryStrip>({
    total_files: 0,
    union_count: 0,
    intersection_count: 0,
    only_a_count: 0,
    only_b_count: 0,
    conflict_count: 0,
  });

  // Loading States
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [recomputing, setRecomputing] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tokenInput) return;
    setLoggingIn(true);
    setLoginError("");
    const ok = await testConnection(tokenInput);
    if (ok) {
      localStorage.setItem("setsync_token", tokenInput);
      setIsAuthenticated(true);
    } else {
      setLoginError("Invalid API Token. Please check backend connection.");
    }
    setLoggingIn(false);
  };
  const [actionLoading, setActionLoading] = useState(false);

  // Modal State
  const [dryRunModal, setDryRunModal] = useState<{
    open: boolean;
    row: UnifiedFileRow | null;
    actionType: "copy" | "move";
    preview: DryRunResponse | null;
  }>({
    open: false,
    row: null,
    actionType: "copy",
    preview: null,
  });

  const [conflictModal, setConflictModal] = useState<{
    open: boolean;
    row: UnifiedFileRow | null;
  }>({
    open: false,
    row: null,
  });

  // Audit Logs State
  const [auditLogs, setAuditLogs] = useState<ActionResponse[]>([]);
  const [auditCount, setAuditCount] = useState(0);

  // Fetch functions
  const fetchStatus = async () => {
    setLoadingStatus(true);
    try {
      const data = await getInventoryStatus();
      setInventoryStatus(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingStatus(false);
    }
  };

  const fetchFiles = async () => {
    setLoadingFiles(true);
    try {
      const data = await getSetsView(viewType, searchQuery || undefined);
      setFiles(data.files);
      setSummary(data.summary);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingFiles(false);
    }
  };

  const fetchLogs = async () => {
    try {
      const data = await getAuditLogs();
      setAuditLogs(data.actions);
      setAuditCount(data.total_count);
    } catch (e) {
      console.error(e);
    }
  };

  // Run on mount
  useEffect(() => {
    if (!isAuthenticated) return;
    fetchStatus();
    fetchFiles();
  }, [viewType, isAuthenticated]);

  // Handle search with debounce/trigger
  useEffect(() => {
    if (!isAuthenticated) return;
    const delay = setTimeout(() => {
      fetchFiles();
    }, 300);
    return () => clearTimeout(delay);
  }, [searchQuery, isAuthenticated]);

  const handleSyncData = async () => {
    setRecomputing(true);
    try {
      await triggerRecompute();
      await fetchStatus();
      await fetchFiles();
      await fetchLogs();
    } catch (e) {
      console.error(e);
    } finally {
      setRecomputing(false);
    }
  };

  const handleOpenDryRun = async (row: UnifiedFileRow, type: "copy" | "move") => {
    setActionLoading(true);
    try {
      const source = row.location === "A" ? "A" : "B";
      const destination = source === "A" ? "B" : "A";
      const preview = await dryRunAction(row.relative_path, source, destination, type);
      setDryRunModal({ open: true, row, actionType: type, preview });
    } catch (e) {
      alert("Error generating dry-run preview: " + e);
    } finally {
      setActionLoading(false);
    }
  };

  const handleExecuteAction = async () => {
    const { row, actionType } = dryRunModal;
    if (!row) return;

    setActionLoading(true);
    try {
      const source = row.location === "A" ? "A" : "B";
      const destination = source === "A" ? "B" : "A";
      
      if (actionType === "copy") {
        await executeCopy(row.relative_path, source, destination);
      } else {
        await executeMove(row.relative_path, source, destination);
      }

      setDryRunModal({ open: false, row: null, actionType: "copy", preview: null });
      await handleSyncData(); // Recompute sets & reload lists
    } catch (e) {
      alert("Execution failed: " + e);
    } finally {
      setActionLoading(false);
    }
  };

  const handleResolveConflict = async (source: "A" | "B") => {
    const { row } = conflictModal;
    if (!row) return;

    setActionLoading(true);
    try {
      const destination = source === "A" ? "B" : "A";
      // To resolve conflict, copy from chosen source to destination
      await executeCopy(row.relative_path, source, destination);
      setConflictModal({ open: false, row: null });
      await handleSyncData();
    } catch (e) {
      alert("Conflict resolution failed: " + e);
    } finally {
      setActionLoading(false);
    }
  };

  const handleUndo = async (actionId: string) => {
    setActionLoading(true);
    try {
      await undoAction(actionId);
      await handleSyncData();
    } catch (e) {
      alert("Undo failed: " + e);
    } finally {
      setActionLoading(false);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const formatDate = (isoString?: string) => {
    if (!isoString) return "-";
    return new Date(isoString).toLocaleString();
  };

  if (!isAuthenticated) {
    return (
      <div className="modal-overlay" style={{ display: "flex", justifyContent: "center", alignItems: "center" }}>
        <div className="modal-content" style={{ maxWidth: "420px", width: "100%", margin: "0 1.5rem", borderRadius: "16px", padding: "2rem" }}>
          <div className="modal-header" style={{ marginBottom: "1.5rem", borderBottom: "none", textAlign: "center", justifyContent: "center" }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.5rem" }}>
              <Database size={44} style={{ color: "var(--accent-cyan)" }} />
              <h2 style={{ fontSize: "1.75rem", fontWeight: "700", color: "var(--text-primary)" }}>SetSync Dashboard</h2>
            </div>
          </div>
          <form onSubmit={handleLogin} className="modal-body" style={{ gap: "1.25rem", padding: 0 }}>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem", textAlign: "center", margin: 0 }}>
              Enter your shared security token to decrypt and unlock this terminal.
            </p>
            <input
              type="password"
              className="search-input"
              style={{ paddingLeft: "1rem", height: "48px", borderRadius: "10px", width: "100%" }}
              placeholder="Security Key..."
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
            />
            {loginError && <p style={{ color: "var(--danger)", fontSize: "0.85rem", textAlign: "center", margin: 0 }}>{loginError}</p>}
            <button 
              type="submit" 
              className="btn btn-primary" 
              style={{ width: "100%", height: "48px", borderRadius: "10px", fontWeight: "600" }}
              disabled={loggingIn}
            >
              {loggingIn ? "Connecting..." : "Decrypt & Access"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header">
        <div className="header-logo">
          <Database size={28} style={{ color: "var(--accent-cyan)" }} />
          <span>SetSync Platform</span>
        </div>
        
        <div className="header-status">
          <div className="status-badge">
            <span className="status-dot"></span>
            <span>Core API Connected</span>
          </div>

          <button 
            className="btn btn-primary" 
            onClick={handleSyncData}
            disabled={recomputing}
          >
            <RefreshCw size={16} className={recomputing ? "animate-spin" : ""} />
            {recomputing ? "Re-syncing..." : "Recompute Sets"}
          </button>

          <button 
            className="btn btn-secondary" 
            onClick={() => {
              localStorage.removeItem("setsync_token");
              setIsAuthenticated(false);
            }}
            style={{ marginLeft: "0.5rem", padding: "0.5rem 1rem", minHeight: "36px" }}
          >
            Lock
          </button>
        </div>
      </header>

      {/* Main Layout */}
      <main className="main-content">
        {/* Navigation Tabs */}
        <div style={{ display: "flex", gap: "1rem" }}>
          <button 
            className={`btn ${activeTab === "dashboard" ? "btn-primary" : ""}`}
            onClick={() => { setActiveTab("dashboard"); fetchFiles(); }}
          >
            <LayoutDashboard size={18} />
            Dashboard
          </button>
          <button 
            className={`btn ${activeTab === "audit" ? "btn-primary" : ""}`}
            onClick={() => { setActiveTab("audit"); fetchLogs(); }}
          >
            <History size={18} />
            Audit Log
          </button>
        </div>

        {activeTab === "dashboard" ? (
          <>
            {/* Live Summary Strip */}
            <section className="summary-grid">
              <div 
                className={`glass-card summary-card union ${viewType === "union" ? "active" : ""}`}
                onClick={() => setViewType("union")}
              >
                <div className="summary-card-info">
                  <h4>Union (All Files)</h4>
                  <div className="count">{summary.union_count}</div>
                </div>
                <div className="summary-card-icon" style={{ color: "var(--accent-blue)" }}>
                  <Database size={24} />
                </div>
              </div>

              <div 
                className={`glass-card summary-card intersection ${viewType === "intersection" ? "active" : ""}`}
                onClick={() => setViewType("intersection")}
              >
                <div className="summary-card-info">
                  <h4>Intersection</h4>
                  <div className="count">{summary.intersection_count}</div>
                </div>
                <div className="summary-card-icon" style={{ color: "var(--success)" }}>
                  <CheckCircle size={24} />
                </div>
              </div>

              <div 
                className={`glass-card summary-card only_a ${viewType === "only_a" ? "active" : ""}`}
                onClick={() => setViewType("only_a")}
              >
                <div className="summary-card-info">
                  <h4>Only PC-A</h4>
                  <div className="count">{summary.only_a_count}</div>
                </div>
                <div className="summary-card-icon" style={{ color: "var(--purple)" }}>
                  <HardDrive size={24} />
                </div>
              </div>

              <div 
                className={`glass-card summary-card only_b ${viewType === "only_b" ? "active" : ""}`}
                onClick={() => setViewType("only_b")}
              >
                <div className="summary-card-info">
                  <h4>Only PC-B</h4>
                  <div className="count">{summary.only_b_count}</div>
                </div>
                <div className="summary-card-icon" style={{ color: "var(--accent-cyan)" }}>
                  <HardDrive size={24} />
                </div>
              </div>

              <div 
                className={`glass-card summary-card conflicts ${viewType === "conflicts" ? "active" : ""}`}
                onClick={() => setViewType("conflicts")}
              >
                <div className="summary-card-info">
                  <h4>Conflicts</h4>
                  <div className="count">{summary.conflict_count}</div>
                </div>
                <div className="summary-card-icon" style={{ color: "var(--danger)" }}>
                  <AlertTriangle size={24} />
                </div>
              </div>
            </section>

            {/* Inventory Status Panel */}
            {inventoryStatus && (
              <section className="glass-card" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem" }}>
                <div>
                  <h3 style={{ marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <HardDrive size={18} style={{ color: "var(--purple)" }} /> PC-A (Local Target A)
                  </h3>
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Total Scanned: <strong>{inventoryStatus.pc_a_count} files</strong></p>
                  <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Last Scan: {formatDate(inventoryStatus.pc_a_last_scan)}</p>
                </div>
                <div>
                  <h3 style={{ marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <HardDrive size={18} style={{ color: "var(--accent-cyan)" }} /> PC-B (Local Target B)
                  </h3>
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Total Scanned: <strong>{inventoryStatus.pc_b_count} files</strong></p>
                  <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Last Scan: {formatDate(inventoryStatus.pc_b_last_scan)}</p>
                </div>
              </section>
            )}

            {/* Search & Filters */}
            <section className="toolbar">
              <div className="search-input-wrapper">
                <Search size={18} className="search-icon" />
                <input 
                  type="text" 
                  className="search-input" 
                  placeholder="Fuzzy search file name, extension or path..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <div className="filter-tabs">
                <button 
                  className={`filter-tab ${viewType === "union" ? "active" : ""}`}
                  onClick={() => setViewType("union")}
                >
                  All Files
                </button>
                <button 
                  className={`filter-tab ${viewType === "intersection" ? "active" : ""}`}
                  onClick={() => setViewType("intersection")}
                >
                  On Both
                </button>
                <button 
                  className={`filter-tab ${viewType === "only_a" ? "active" : ""}`}
                  onClick={() => setViewType("only_a")}
                >
                  Only PC-A
                </button>
                <button 
                  className={`filter-tab ${viewType === "only_b" ? "active" : ""}`}
                  onClick={() => setViewType("only_b")}
                >
                  Only PC-B
                </button>
                <button 
                  className={`filter-tab ${viewType === "conflicts" ? "active" : ""}`}
                  onClick={() => setViewType("conflicts")}
                >
                  Conflicts
                </button>
              </div>
            </section>

            {/* Files Table */}
            <section className="glass-card" style={{ padding: 0 }}>
              <div className="table-container">
                {loadingFiles ? (
                  <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-secondary)" }}>
                    <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 1rem" }} />
                    Loading files snapshot...
                  </div>
                ) : files.length === 0 ? (
                  <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
                    No files found matching criteria.
                  </div>
                ) : (
                  <table className="file-table">
                    <thead>
                      <tr>
                        <th>File Name & Path</th>
                        <th>Size</th>
                        <th>Location</th>
                        <th>SHA-256 Hash</th>
                        <th style={{ textAlign: "right" }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {files.map((file) => (
                        <tr key={file.id}>
                          <td>
                            <div className="file-name-cell">
                              <FileCode size={20} style={{ color: "var(--text-secondary)" }} />
                              <div>
                                <div>{file.name}</div>
                                <div className="file-path">{file.relative_path}</div>
                              </div>
                            </div>
                          </td>
                          <td>{formatSize(file.size_bytes)}</td>
                          <td>
                            <span className={`location-indicator ${file.location.toLowerCase()}`}>
                              {file.location === "Both" ? "Both PCs" : file.location === "Conflict" ? "Conflict" : `PC-${file.location}`}
                            </span>
                          </td>
                          <td>
                            <span className="file-hash" title={file.hash_sha256}>
                              {file.hash_sha256.substring(0, 8)}...
                            </span>
                          </td>
                          <td style={{ textAlign: "right" }}>
                            {file.location === "A" && (
                              <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
                                <button 
                                  className="btn btn-sm btn-primary"
                                  onClick={() => handleOpenDryRun(file, "copy")}
                                >
                                  Copy to B
                                </button>
                                <button 
                                  className="btn btn-sm"
                                  onClick={() => handleOpenDryRun(file, "move")}
                                >
                                  Move to B
                                </button>
                              </div>
                            )}
                            {file.location === "B" && (
                              <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
                                <button 
                                  className="btn btn-sm btn-primary"
                                  onClick={() => handleOpenDryRun(file, "copy")}
                                >
                                  Copy to A
                                </button>
                                <button 
                                  className="btn btn-sm"
                                  onClick={() => handleOpenDryRun(file, "move")}
                                >
                                  Move to A
                                </button>
                              </div>
                            )}
                            {file.location === "Both" && (
                              <span style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginRight: "0.5rem" }}>
                                Synchronized
                              </span>
                            )}
                            {file.location === "Conflict" && (
                              <button 
                                className="btn btn-sm btn-danger"
                                onClick={() => setConflictModal({ open: true, row: file })}
                              >
                                Resolve
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </section>
          </>
        ) : (
          /* Audit Logs View */
          <section className="glass-card" style={{ padding: 0 }}>
            <div className="table-container">
              <table className="file-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Action</th>
                    <th>File</th>
                    <th>From</th>
                    <th>To</th>
                    <th>Status</th>
                    <th style={{ textAlign: "right" }}>Revert</th>
                  </tr>
                </thead>
                <tbody>
                  {auditLogs.length === 0 ? (
                    <tr>
                      <td colSpan={7} style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>
                        No audit records yet.
                      </td>
                    </tr>
                  ) : (
                    auditLogs.map((log) => (
                      <tr key={log.id}>
                        <td>{formatDate(log.timestamp)}</td>
                        <td style={{ fontWeight: 600 }}>{log.action_type.toUpperCase()}</td>
                        <td className="file-path">{log.file_path}</td>
                        <td>PC-{log.source}</td>
                        <td>PC-{log.destination}</td>
                        <td>
                          <span className={`audit-status ${log.status.toLowerCase()}`}>
                            {log.status}
                          </span>
                        </td>
                        <td style={{ textAlign: "right" }}>
                          {log.status === "completed" && (log.action_type === "copy" || log.action_type === "move") ? (
                            <button 
                              className="btn btn-sm btn-danger"
                              onClick={() => handleUndo(log.id)}
                              disabled={actionLoading}
                            >
                              <Undo size={14} />
                              Undo
                            </button>
                          ) : log.status === "undone" ? (
                            <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Reverted</span>
                          ) : (
                            "-"
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </main>

      {/* Dry Run modal */}
      {dryRunModal.open && dryRunModal.preview && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Confirm Execution Preview</h3>
              <button 
                className="close-btn"
                onClick={() => setDryRunModal({ open: false, row: null, actionType: "copy", preview: null })}
              >
                ✕
              </button>
            </div>
            
            <div className="modal-body">
              <p style={{ color: "var(--text-secondary)" }}>
                You are executing a <strong>{dryRunModal.actionType}</strong> operation. Below is the pre-action preview:
              </p>
              
              <div className="glass-card" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                <div><strong>File:</strong> <span className="file-path">{dryRunModal.row?.relative_path}</span></div>
                <div><strong>From:</strong> PC-{dryRunModal.preview.source} ➔ <strong>To:</strong> PC-{dryRunModal.preview.destination}</div>
                <div><strong>Overwrite target?</strong> {dryRunModal.preview.will_overwrite ? "Yes (WARNING)" : "No"}</div>
              </div>

              {dryRunModal.preview.will_overwrite ? (
                <div style={{ color: "var(--danger)", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <AlertTriangle size={20} />
                  <span><strong>Warning:</strong> {dryRunModal.preview.message}</span>
                </div>
              ) : (
                <div style={{ color: "var(--success)", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <CheckCircle size={20} />
                  <span>{dryRunModal.preview.message}</span>
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button 
                className="btn"
                onClick={() => setDryRunModal({ open: false, row: null, actionType: "copy", preview: null })}
              >
                Cancel
              </button>
              <button 
                className={`btn ${dryRunModal.preview.will_overwrite ? "btn-danger" : "btn-primary"}`}
                onClick={handleExecuteAction}
                disabled={actionLoading}
              >
                {actionLoading ? "Executing..." : "Confirm & Execute"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Conflict resolution modal */}
      {conflictModal.open && conflictModal.row && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: "700px" }}>
            <div className="modal-header">
              <h3>Resolve File Conflict</h3>
              <button 
                className="close-btn"
                onClick={() => setConflictModal({ open: false, row: null })}
              >
                ✕
              </button>
            </div>
            
            <div className="modal-body">
              <p style={{ color: "var(--text-secondary)" }}>
                Same file path found on both machines, but content hashes differ. Select which version to keep:
              </p>
              
              <div className="comparison-container">
                <div className="comparison-box">
                  <div className="comparison-box-header">
                    <span>Keep PC-A version</span>
                    <HardDrive size={18} style={{ color: "var(--purple)" }} />
                  </div>
                  <div className="meta-row">
                    <span className="meta-label">Size:</span>
                    <span className="meta-val">{formatSize(conflictModal.row.size_bytes)}</span>
                  </div>
                  <div className="meta-row">
                    <span className="meta-label">Modified:</span>
                    <span className="meta-val">{formatDate(conflictModal.row.mtime_a)}</span>
                  </div>
                  <div className="meta-row">
                    <span className="meta-label">Hash:</span>
                    <span className="meta-val">{conflictModal.row.hash_sha256.substring(0, 12)}</span>
                  </div>
                  <button 
                    className="btn btn-primary btn-sm"
                    style={{ marginTop: "1rem" }}
                    onClick={() => handleResolveConflict("A")}
                    disabled={actionLoading}
                  >
                    Select PC-A Version
                  </button>
                </div>

                <div className="comparison-box">
                  <div className="comparison-box-header">
                    <span>Keep PC-B version</span>
                    <HardDrive size={18} style={{ color: "var(--accent-cyan)" }} />
                  </div>
                  <div className="meta-row">
                    <span className="meta-label">Size:</span>
                    <span className="meta-val">{formatSize(conflictModal.row.size_bytes)}</span>
                  </div>
                  <div className="meta-row">
                    <span className="meta-label">Modified:</span>
                    <span className="meta-val">{formatDate(conflictModal.row.mtime_b)}</span>
                  </div>
                  <div className="meta-row">
                    <span className="meta-label">Hash:</span>
                    <span className="meta-val">{conflictModal.row.hash_sha256.substring(0, 12)}</span>
                  </div>
                  <button 
                    className="btn btn-primary btn-sm"
                    style={{ marginTop: "1rem" }}
                    onClick={() => handleResolveConflict("B")}
                    disabled={actionLoading}
                  >
                    Select PC-B Version
                  </button>
                </div>
              </div>
            </div>

            <div className="modal-footer">
              <button 
                className="btn"
                onClick={() => setConflictModal({ open: false, row: null })}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
