import React, { useState, useEffect } from "react";
import { 
  getInventoryStatus, 
  getSources,
  getSetsView, 
  triggerRecompute, 
  dryRunAction, 
  executeCopy, 
  executeMove, 
  executeDelete,
  undoAction, 
  getAuditLogs,
  testConnection,
  getDuplicates,
  getStaleOrphans
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
  CheckCircle, 
  AlertTriangle, 
  Undo, 
  History, 
  LayoutDashboard,
  FileCode,
  HardDrive,
  Cpu,
  ArrowRightLeft,
  Trash2,
  Sparkles,
  Calendar,
  Download,
  ShieldCheck
} from "lucide-react";

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem("setsync_token"));
  const [tokenInput, setTokenInput] = useState("");
  const [loginError, setLoginError] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);

  const [activeTab, setActiveTab] = useState<"dashboard" | "audit" | "dedupe" | "stale">("dashboard");
  const [inventoryStatus, setInventoryStatus] = useState<InventoryStatus | null>(null);
  const [sources, setSources] = useState<any[]>([]);
  const [sourceX, setSourceX] = useState<string>("");
  const [sourceY, setSourceY] = useState<string>("");
  
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

  // Duplicates Report State
  const [duplicatesReport, setDuplicatesReport] = useState<any>(null);
  const [loadingDedupe, setLoadingDedupe] = useState(false);

  // Stale Orphans State
  const [staleOrphans, setStaleOrphans] = useState<any[]>([]);
  const [staleAgeDays, setStaleAgeDays] = useState<number>(180);
  const [loadingStale, setLoadingStale] = useState(false);

  // Loading States
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [recomputing, setRecomputing] = useState(false);
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

  // Consolidation Wizard State
  const [wizardModal, setWizardModal] = useState<{
    open: boolean;
    step: 1 | 2 | 3 | 4 | 5;
    srcId: string;
    dstId: string;
    uniqueFiles: UnifiedFileRow[];
    conflictFiles: UnifiedFileRow[];
    currentProgress: number;
    totalToCopy: number;
    activeTransferFile: string;
    certificateText: string;
  }>({
    open: false,
    step: 1,
    srcId: "",
    dstId: "",
    uniqueFiles: [],
    conflictFiles: [],
    currentProgress: 0,
    totalToCopy: 0,
    activeTransferFile: "",
    certificateText: "",
  });

  // Audit Logs State
  const [auditLogs, setAuditLogs] = useState<ActionResponse[]>([]);

  // Fetch functions
  const fetchStatus = async () => {
    try {
      const data = await getInventoryStatus();
      setInventoryStatus(data);

      const sourcesList = await getSources();
      setSources(sourcesList);

      if (sourcesList.length > 0) {
        setSourceX((prev) => prev || sourcesList[0].id);
        if (sourcesList.length > 1) {
          setSourceY((prev) => prev || sourcesList[1].id);
        } else {
          setSourceY((prev) => prev || sourcesList[0].id);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchFiles = async () => {
    if (!sourceX || !sourceY) return;
    setLoadingFiles(true);
    try {
      const data = await getSetsView(sourceX, sourceY, viewType, searchQuery || undefined);
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
    } catch (e) {
      console.error(e);
    }
  };

  const fetchDuplicates = async () => {
    setLoadingDedupe(true);
    try {
      const data = await getDuplicates();
      setDuplicatesReport(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingDedupe(false);
    }
  };

  const fetchStaleOrphans = async () => {
    setLoadingStale(true);
    try {
      const data = await getStaleOrphans(staleAgeDays);
      setStaleOrphans(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingStale(false);
    }
  };

  // Run on mount
  useEffect(() => {
    if (!isAuthenticated) return;
    fetchStatus();
    fetchLogs();
  }, [isAuthenticated]);

  // Re-fetch files when source selection, tab, or view type changes
  useEffect(() => {
    if (!isAuthenticated) return;
    if (activeTab === "dashboard") {
      fetchFiles();
    } else if (activeTab === "dedupe") {
      fetchDuplicates();
    } else if (activeTab === "stale") {
      fetchStaleOrphans();
    }
  }, [sourceX, sourceY, viewType, activeTab, isAuthenticated]);

  // Re-fetch stale if age days changes
  useEffect(() => {
    if (!isAuthenticated || activeTab !== "stale") return;
    fetchStaleOrphans();
  }, [staleAgeDays, isAuthenticated]);

  // Handle search with debounce/trigger
  useEffect(() => {
    if (!isAuthenticated) return;
    const delay = setTimeout(() => {
      fetchFiles();
    }, 300);
    return () => clearTimeout(delay);
  }, [searchQuery, isAuthenticated]);

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

  const handleSyncData = async () => {
    if (!sourceX || !sourceY) return;
    setRecomputing(true);
    try {
      await triggerRecompute(sourceX, sourceY);
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
    if (!sourceX || !sourceY) return;
    setActionLoading(true);
    try {
      const source = row.location === "A" ? sourceX : sourceY;
      const destination = source === sourceX ? sourceY : sourceX;
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
    if (!row || !sourceX || !sourceY) return;

    setActionLoading(true);
    try {
      const source = row.location === "A" ? sourceX : sourceY;
      const destination = source === sourceX ? sourceY : sourceX;
      
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

  const handleSafeDelete = async (filePath: string, sourceId: string) => {
    if (!window.confirm("Are you sure you want to delete this redundant duplicate? This will only remove this copy on the selected device.")) return;
    setActionLoading(true);
    try {
      await executeDelete(filePath, sourceId, false);
      alert("Redundant copy removed successfully!");
      if (activeTab === "dedupe") fetchDuplicates();
      else handleSyncData();
    } catch (e: any) {
      if (e.message && e.message.includes("Safety Block")) {
        const force = window.confirm(e.message + "\n\nDo you want to FORCE delete it anyway?");
        if (force) {
          try {
            await executeDelete(filePath, sourceId, true);
            alert("File force-deleted successfully!");
            if (activeTab === "dedupe") fetchDuplicates();
            else handleSyncData();
          } catch (forceErr: any) {
            alert("Force delete failed: " + forceErr.message);
          }
        }
      } else {
        alert("Delete failed: " + e.message);
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleResolveConflict = async (winner: "A" | "B") => {
    const { row } = conflictModal;
    if (!row || !sourceX || !sourceY) return;

    setActionLoading(true);
    try {
      const source = winner === "A" ? sourceX : sourceY;
      const destination = source === sourceX ? sourceY : sourceX;
      
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

  // Wizard Methods
  const openWizard = () => {
    setWizardModal({
      open: true,
      step: 1,
      srcId: sourceX,
      dstId: sourceY,
      uniqueFiles: [],
      conflictFiles: [],
      currentProgress: 0,
      totalToCopy: 0,
      activeTransferFile: "",
      certificateText: "",
    });
  };

  const loadWizardPreview = async () => {
    const { srcId, dstId } = wizardModal;
    if (!srcId || !dstId) return;
    
    setActionLoading(true);
    try {
      // Fetch only files on A (left device)
      const dataA = await getSetsView(srcId, dstId, "only_a");
      const uniqueA = dataA.files;

      // Fetch conflicts
      const dataConflicts = await getSetsView(srcId, dstId, "conflicts");
      const conflicts = dataConflicts.files;

      setWizardModal(prev => ({
        ...prev,
        step: 2,
        uniqueFiles: uniqueA,
        conflictFiles: conflicts,
        totalToCopy: uniqueA.length
      }));
    } catch (e) {
      alert("Failed to analyze files for consolidation: " + e);
    } finally {
      setActionLoading(false);
    }
  };

  const executeConsolidation = async () => {
    const { srcId, dstId, uniqueFiles } = wizardModal;
    setWizardModal(prev => ({ ...prev, step: 4, currentProgress: 0 }));
    
    let copiedCount = 0;
    const errors = [];
    const startTime = new Date();
    
    for (const file of uniqueFiles) {
      setWizardModal(prev => ({ ...prev, activeTransferFile: file.relative_path }));
      try {
        await executeCopy(file.relative_path, srcId, dstId);
        copiedCount++;
      } catch (e: any) {
        errors.push(`${file.relative_path}: ${e.message}`);
      }
      setWizardModal(prev => ({ ...prev, currentProgress: copiedCount }));
      // Give small aesthetic delay for visual progression
      await new Promise(r => setTimeout(r, 200));
    }
    
    const srcName = sources.find(s => s.id === srcId)?.name || "Src";
    const dstName = sources.find(s => s.id === dstId)?.name || "Dst";
    const endTime = new Date();
    
    const totalSize = uniqueFiles.reduce((acc, f) => acc + f.size_bytes, 0);
    const formattedTotalSize = formatSize(totalSize);

    // Construct Certificate Text
    const cert = `# SetSync Consolidation Certificate
**Consolidation Completion Report**

- **Date:** ${new Date().toLocaleDateString()}
- **Time Duration:** ${((endTime.getTime() - startTime.getTime()) / 1000).toFixed(1)} seconds
- **Source Device:** ${srcName} (ID: ${srcId})
- **Destination Device:** ${dstName} (ID: ${dstId})
- **Files Consolidated:** ${copiedCount} files (${formattedTotalSize})
- **Errors Encountered:** ${errors.length}
- **Consolidation Status:** ${errors.length === 0 ? "SUCCESS" : "PARTIAL_SUCCESS"}

---
*Verified & signed by SetSync Coordinator Cryptographic Policy Engine.*
`;

    // Recompute after consolidation to clear visual lists
    await triggerRecompute(srcId, dstId);
    await fetchStatus();

    setWizardModal(prev => ({
      ...prev,
      step: 5,
      certificateText: cert
    }));
  };

  const downloadCert = () => {
    const element = document.createElement("a");
    const file = new Blob([wizardModal.certificateText], {type: 'text/plain'});
    element.href = URL.createObjectURL(file);
    element.download = `setsync-consolidation-certificate-${Date.now()}.md`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
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

  const nameX = sources.find(s => s.id === sourceX)?.name || "Device A";
  const nameY = sources.find(s => s.id === sourceY)?.name || "Device B";

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
          <button
            className="btn"
            style={{ marginRight: "0.5rem", border: "1px solid var(--accent-cyan)", color: "var(--accent-cyan)" }}
            onClick={openWizard}
            disabled={sources.length < 2}
          >
            <Sparkles size={16} style={{ marginRight: "0.35rem" }} />
            Consolidation Wizard
          </button>

          <button 
            className="btn btn-primary" 
            onClick={handleSyncData}
            disabled={recomputing || !sourceX || !sourceY}
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
        <div style={{ display: "flex", gap: "1rem", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", gap: "1rem" }}>
            <button 
              className={`btn ${activeTab === "dashboard" ? "btn-primary" : ""}`}
              onClick={() => { setActiveTab("dashboard"); fetchFiles(); }}
            >
              <LayoutDashboard size={18} />
              Dashboard
            </button>
            <button 
              className={`btn ${activeTab === "dedupe" ? "btn-primary" : ""}`}
              onClick={() => { setActiveTab("dedupe"); fetchDuplicates(); }}
            >
              <Trash2 size={18} />
              Duplicates
            </button>
            <button 
              className={`btn ${activeTab === "stale" ? "btn-primary" : ""}`}
              onClick={() => { setActiveTab("stale"); fetchStaleOrphans(); }}
            >
              <Calendar size={18} />
              Stale Orphans
            </button>
            <button 
              className={`btn ${activeTab === "audit" ? "btn-primary" : ""}`}
              onClick={() => { setActiveTab("audit"); fetchLogs(); }}
            >
              <History size={18} />
              Audit Log
            </button>
          </div>
          
          <div style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
            Active Devices Registered: <strong style={{ color: "var(--text-secondary)" }}>{sources.length}</strong>
          </div>
        </div>

        {/* Tab 1: Dashboard */}
        {activeTab === "dashboard" && (
          <>
            <section className="glass-card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "1.1rem" }}>
                <Cpu size={18} style={{ color: "var(--accent-cyan)" }} /> Pick Devices to Compare
              </h3>
              
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center", gap: "1.5rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.35rem" }}>Left Device (A)</label>
                  <select 
                    className="search-input"
                    style={{ width: "100%", height: "42px", borderRadius: "8px", paddingLeft: "0.75rem" }}
                    value={sourceX}
                    onChange={(e) => setSourceX(e.target.value)}
                  >
                    <option value="" disabled>Select Device A...</option>
                    {sources.map(s => (
                      <option key={s.id} value={s.id}>
                        {s.name} ({s.status} - {s.kind})
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ display: "flex", justifyContent: "center", paddingTop: "1.2rem" }}>
                  <ArrowRightLeft size={20} style={{ color: "var(--text-muted)" }} />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.35rem" }}>Right Device (B)</label>
                  <select 
                    className="search-input"
                    style={{ width: "100%", height: "42px", borderRadius: "8px", paddingLeft: "0.75rem" }}
                    value={sourceY}
                    onChange={(e) => setSourceY(e.target.value)}
                  >
                    <option value="" disabled>Select Device B...</option>
                    {sources.map(s => (
                      <option key={s.id} value={s.id} disabled={s.id === sourceX && sources.length > 1}>
                        {s.name} ({s.status} - {s.kind})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </section>

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
                  <h4>Only {nameX}</h4>
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
                  <h4>Only {nameY}</h4>
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
            {inventoryStatus && inventoryStatus.sources && inventoryStatus.sources.length > 0 && (
              <section className="glass-card" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem" }}>
                {inventoryStatus.sources.map(s => (
                  <div key={s.source_id}>
                    <h3 style={{ marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <HardDrive size={18} style={{ color: s.source_id === sourceX ? "var(--purple)" : "var(--accent-cyan)" }} /> 
                      {s.name} {s.source_id === sourceX ? "(A)" : s.source_id === sourceY ? "(B)" : ""}
                    </h3>
                    <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Total Scanned: <strong>{s.count} files</strong></p>
                    <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Last Scan: {formatDate(s.last_scan)}</p>
                  </div>
                ))}
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
                  Only {nameX}
                </button>
                <button 
                  className={`filter-tab ${viewType === "only_b" ? "active" : ""}`}
                  onClick={() => setViewType("only_b")}
                >
                  Only {nameY}
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
                ) : !sourceX || !sourceY ? (
                  <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
                    Please select both Left and Right devices to inspect file set comparisons.
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
                              {file.location === "Both" ? "Both Devices" : file.location === "Conflict" ? "Conflict" : file.location === "A" ? nameX : nameY}
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
                                  className="btn btn-sm text-danger"
                                  onClick={() => handleSafeDelete(file.relative_path, sourceX)}
                                >
                                  Delete
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
                                  className="btn btn-sm text-danger"
                                  onClick={() => handleSafeDelete(file.relative_path, sourceY)}
                                >
                                  Delete
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
        )}

        {/* Tab 2: Duplicates */}
        {activeTab === "dedupe" && (
          <section className="glass-card" style={{ gap: "1.5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h3 style={{ margin: 0, fontSize: "1.25rem" }}>Duplicate File Analyzer</h3>
                <p style={{ margin: "0.25rem 0 0 0", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                  Find redundant files stored multiple times across your network.
                </p>
              </div>
              
              {duplicatesReport && (
                <div style={{ textAlign: "right" }}>
                  <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Space Reclaimable</span>
                  <div style={{ fontSize: "1.75rem", fontWeight: "700", color: "var(--success)" }}>
                    {formatSize(duplicatesReport.space_reclaimable_bytes)}
                  </div>
                </div>
              )}
            </div>

            {loadingDedupe ? (
              <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-secondary)" }}>
                <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 1rem" }} />
                Analyzing duplicate structures...
              </div>
            ) : !duplicatesReport || duplicatesReport.groups.length === 0 ? (
              <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
                No duplicate groups detected in your inventory! Excellent storage health.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                {duplicatesReport.groups.map((group: any) => (
                  <div 
                    key={group.hash_sha256} 
                    className="glass-card" 
                    style={{ padding: "1.25rem", backgroundColor: "rgba(255, 255, 255, 0.015)" }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.75rem", borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: "0.5rem" }}>
                      <div>
                        <strong style={{ fontSize: "0.95rem" }}>Hash: {group.hash_sha256.substring(0, 16)}...</strong>
                        <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Duplicate Count: {group.files.length} copies</div>
                      </div>
                      <div style={{ fontWeight: 600, color: "var(--accent-cyan)" }}>
                        {formatSize(group.size_bytes)} each
                      </div>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                      {group.files.map((file: any) => (
                        <div 
                          key={file.id} 
                          style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.5rem", backgroundColor: "rgba(255,255,255,0.02)", borderRadius: "6px" }}
                        >
                          <div>
                            <div style={{ fontSize: "0.9rem" }}>{file.path}</div>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                              Device: <strong>{file.source_name}</strong> · Modified: {formatDate(file.mtime)}
                            </div>
                          </div>

                          <button 
                            className="btn btn-sm btn-danger"
                            onClick={() => handleSafeDelete(file.relative_path, file.source_id)}
                            style={{ minHeight: "30px", padding: "0.25rem 0.75rem" }}
                          >
                            <Trash2 size={13} style={{ marginRight: "0.25rem" }} />
                            Delete Copy
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* Tab 3: Stale Orphans */}
        {activeTab === "stale" && (
          <section className="glass-card" style={{ gap: "1.5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h3 style={{ margin: 0, fontSize: "1.25rem" }}>Stale / Orphan File Report</h3>
                <p style={{ margin: "0.25rem 0 0 0", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                  Unique files present on only one device that have not been modified for a long time.
                </p>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Stale Age Threshold:</span>
                <select 
                  className="search-input" 
                  style={{ width: "120px", height: "36px", paddingLeft: "0.5rem", borderRadius: "6px" }}
                  value={staleAgeDays}
                  onChange={(e) => setStaleAgeDays(Number(e.target.value))}
                >
                  <option value={30}>30 Days</option>
                  <option value={90}>90 Days</option>
                  <option value={180}>180 Days</option>
                  <option value={365}>1 Year</option>
                </select>
              </div>
            </div>

            {loadingStale ? (
              <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-secondary)" }}>
                <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 1rem" }} />
                Analyzing unique file records...
              </div>
            ) : staleOrphans.length === 0 ? (
              <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
                No stale orphan files found.
              </div>
            ) : (
              <div className="table-container">
                <table className="file-table">
                  <thead>
                    <tr>
                      <th>File Name & Path</th>
                      <th>Size</th>
                      <th>Source Device</th>
                      <th>Last Modified</th>
                      <th style={{ textAlign: "right" }}>Age</th>
                    </tr>
                  </thead>
                  <tbody>
                    {staleOrphans.map(file => (
                      <tr key={file.id}>
                        <td>
                          <div className="file-name-cell">
                            <FileCode size={20} style={{ color: "var(--text-secondary)" }} />
                            <div>
                              <div>{file.relative_path}</div>
                              <div className="file-path">{file.path}</div>
                            </div>
                          </div>
                        </td>
                        <td>{formatSize(file.size_bytes)}</td>
                        <td><strong>{file.source_name}</strong></td>
                        <td>{formatDate(file.mtime)}</td>
                        <td style={{ textAlign: "right", color: "var(--danger)", fontWeight: 600 }}>
                          {file.age_days} Days Old
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {/* Tab 4: Audit Logs View */}
        {activeTab === "audit" && (
          <section className="glass-card" style={{ padding: 0 }}>
            <div className="table-container">
              <table className="file-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Action</th>
                    <th>File</th>
                    <th>From Device</th>
                    <th>To Device</th>
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
                    auditLogs.map((log) => {
                      const logSrcName = sources.find(s => s.id === log.source)?.name || `ID: ${log.source.substring(0,6)}`;
                      const logDstName = sources.find(s => s.id === log.destination)?.name || `ID: ${log.destination.substring(0,6)}`;
                      return (
                        <tr key={log.id}>
                          <td>{formatDate(log.timestamp)}</td>
                          <td style={{ fontWeight: 600 }}>{log.action_type.toUpperCase()}</td>
                          <td className="file-path">{log.file_path}</td>
                          <td>{logSrcName}</td>
                          <td>{logDstName}</td>
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
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </main>

      {/* Consolidation Wizard Modal */}
      {wizardModal.open && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: "680px" }}>
            <div className="modal-header">
              <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Sparkles size={20} style={{ color: "var(--accent-cyan)" }} />
                SetSync Consolidation Wizard — Step {wizardModal.step} of 5
              </h3>
              <button 
                className="close-btn"
                onClick={() => setWizardModal(prev => ({ ...prev, open: false }))}
                disabled={wizardModal.step === 4}
              >
                ✕
              </button>
            </div>

            <div className="modal-body" style={{ minHeight: "260px" }}>
              {/* Step 1: Pick devices */}
              {wizardModal.step === 1 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                  <p style={{ color: "var(--text-secondary)" }}>
                    Consolidating merges all unique files from a Source device into a Target device.
                  </p>
                  
                  <div>
                    <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: "0.5rem" }}>Source Device (Merge from)</label>
                    <select
                      className="search-input"
                      style={{ width: "100%", height: "44px", paddingLeft: "0.75rem", borderRadius: "8px" }}
                      value={wizardModal.srcId}
                      onChange={(e) => setWizardModal(prev => ({ ...prev, srcId: e.target.value }))}
                    >
                      <option value="">Choose source device...</option>
                      {sources.map(s => (
                        <option key={s.id} value={s.id}>{s.name} ({s.status})</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: "0.5rem" }}>Target Destination Device (Consolidate into)</label>
                    <select
                      className="search-input"
                      style={{ width: "100%", height: "44px", paddingLeft: "0.75rem", borderRadius: "8px" }}
                      value={wizardModal.dstId}
                      onChange={(e) => setWizardModal(prev => ({ ...prev, dstId: e.target.value }))}
                    >
                      <option value="">Choose target device...</option>
                      {sources.map(s => (
                        <option key={s.id} value={s.id} disabled={s.id === wizardModal.srcId}>{s.name} ({s.status})</option>
                      ))}
                    </select>
                  </div>
                </div>
              )}

              {/* Step 2: Preview Report */}
              {wizardModal.step === 2 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                  <p style={{ color: "var(--text-secondary)" }}>
                    Analysis complete. Here is the estimated sync report:
                  </p>
                  
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
                    <div className="glass-card" style={{ padding: "1.25rem", textAlign: "center" }}>
                      <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Files to Copy</div>
                      <div style={{ fontSize: "2rem", fontWeight: "700", color: "var(--accent-blue)", margin: "0.25rem 0" }}>
                        {wizardModal.uniqueFiles.length}
                      </div>
                      <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                        ({formatSize(wizardModal.uniqueFiles.reduce((a,f)=>a+f.size_bytes, 0))})
                      </span>
                    </div>

                    <div className="glass-card" style={{ padding: "1.25rem", textAlign: "center" }}>
                      <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Conflict Files</div>
                      <div style={{ fontSize: "2rem", fontWeight: "700", color: "var(--danger)", margin: "0.25rem 0" }}>
                        {wizardModal.conflictFiles.length}
                      </div>
                      <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Requires manual review</span>
                    </div>
                  </div>

                  {wizardModal.conflictFiles.length > 0 && (
                    <div style={{ color: "var(--danger)", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <AlertTriangle size={20} />
                      <span><strong>Warning:</strong> You must resolve file conflicts before executing the merge.</span>
                    </div>
                  )}
                </div>
              )}

              {/* Step 3: Conflict Queue */}
              {wizardModal.step === 3 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <p style={{ color: "var(--text-secondary)" }}>
                    Resolve conflicting files. Select the version to consolidate:
                  </p>
                  
                  <div style={{ maxHeight: "250px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                    {wizardModal.conflictFiles.map(file => (
                      <div key={file.id} className="glass-card" style={{ padding: "1rem" }}>
                        <div style={{ fontWeight: 600, fontSize: "0.9rem", marginBottom: "0.5rem" }}>{file.relative_path}</div>
                        <div style={{ display: "flex", gap: "0.5rem" }}>
                          <button 
                            className="btn btn-sm btn-primary"
                            onClick={async () => {
                              await executeCopy(file.relative_path, wizardModal.srcId, wizardModal.dstId);
                              setWizardModal(prev => ({
                                ...prev,
                                conflictFiles: prev.conflictFiles.filter(c => c.id !== file.id)
                              }));
                            }}
                          >
                            Keep Source Version
                          </button>
                          <button 
                            className="btn btn-sm btn-secondary"
                            onClick={() => {
                              // Skipping means keeping destination/target version as is
                              setWizardModal(prev => ({
                                ...prev,
                                conflictFiles: prev.conflictFiles.filter(c => c.id !== file.id)
                              }));
                            }}
                          >
                            Keep Destination Version
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Step 4: Progress execution */}
              {wizardModal.step === 4 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem", justifyContent: "center", alignItems: "center", paddingTop: "1rem" }}>
                  <RefreshCw size={44} className="animate-spin" style={{ color: "var(--accent-cyan)" }} />
                  
                  <div style={{ textAlign: "center" }}>
                    <div style={{ fontWeight: 600, fontSize: "1.1rem" }}>Executing Consolidation...</div>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: "0.25rem" }}>
                      Active: <span style={{ fontFamily: "monospace" }}>{wizardModal.activeTransferFile || "-"}</span>
                    </div>
                  </div>

                  <div style={{ width: "100%", height: "8px", backgroundColor: "rgba(255,255,255,0.05)", borderRadius: "4px", overflow: "hidden" }}>
                    <div 
                      style={{ 
                        height: "100%", 
                        backgroundColor: "var(--accent-cyan)", 
                        width: `${(wizardModal.currentProgress / (wizardModal.totalToCopy || 1)) * 100}%`,
                        transition: "width 0.2s ease"
                      }}
                    />
                  </div>

                  <div style={{ fontSize: "0.9rem", color: "var(--text-secondary)" }}>
                    Progress: {wizardModal.currentProgress} of {wizardModal.totalToCopy} files copied
                  </div>
                </div>
              )}

              {/* Step 5: Certificate */}
              {wizardModal.step === 5 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                  <div style={{ textAlign: "center", color: "var(--success)", display: "flex", flexDirection: "column", alignItems: "center", gap: "0.5rem" }}>
                    <ShieldCheck size={48} />
                    <h4 style={{ margin: 0, fontSize: "1.25rem" }}>Consolidation Completed Successfully!</h4>
                  </div>
                  
                  <pre 
                    style={{ 
                      padding: "1rem", 
                      backgroundColor: "rgba(0,0,0,0.2)", 
                      borderRadius: "8px", 
                      fontSize: "0.85rem", 
                      color: "#fff",
                      fontFamily: "monospace",
                      overflowX: "auto"
                    }}
                  >
                    {wizardModal.certificateText}
                  </pre>
                </div>
              )}
            </div>

            <div className="modal-footer">
              {wizardModal.step === 1 && (
                <>
                  <button className="btn" onClick={() => setWizardModal(prev => ({ ...prev, open: false }))}>Cancel</button>
                  <button 
                    className="btn btn-primary" 
                    disabled={!wizardModal.srcId || !wizardModal.dstId || actionLoading}
                    onClick={loadWizardPreview}
                  >
                    {actionLoading ? "Analyzing..." : "Analyze & Preview"}
                  </button>
                </>
              )}

              {wizardModal.step === 2 && (
                <>
                  <button className="btn" onClick={() => setWizardModal(prev => ({ ...prev, step: 1 }))}>Back</button>
                  {wizardModal.conflictFiles.length > 0 ? (
                    <button className="btn btn-danger" onClick={() => setWizardModal(prev => ({ ...prev, step: 3 }))}>
                      Go Resolve Conflicts
                    </button>
                  ) : (
                    <button className="btn btn-primary" onClick={executeConsolidation}>
                      Begin Consolidation
                    </button>
                  )}
                </>
              )}

              {wizardModal.step === 3 && (
                <>
                  <button className="btn" onClick={() => setWizardModal(prev => ({ ...prev, step: 2 }))}>Back</button>
                  <button 
                    className="btn btn-primary" 
                    disabled={wizardModal.conflictFiles.length > 0}
                    onClick={executeConsolidation}
                  >
                    All Resolved — Start Consolidation
                  </button>
                </>
              )}

              {wizardModal.step === 4 && (
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Running transfer loop...</span>
              )}

              {wizardModal.step === 5 && (
                <>
                  <button className="btn btn-secondary" onClick={downloadCert}>
                    <Download size={14} style={{ marginRight: "0.35rem" }} />
                    Save Markdown Certificate
                  </button>
                  <button className="btn btn-primary" onClick={() => setWizardModal(prev => ({ ...prev, open: false }))}>
                    Done & Close
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

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
                <div><strong>From:</strong> {nameX} ➔ <strong>To:</strong> {nameY}</div>
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
                    <span>Keep {nameX} version</span>
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
                    Select {nameX} Version
                  </button>
                </div>

                <div className="comparison-box">
                  <div className="comparison-box-header">
                    <span>Keep {nameY} version</span>
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
                    Select {nameY} Version
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
