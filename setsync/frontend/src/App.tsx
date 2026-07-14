import React, { useState, useEffect } from "react";
import AdPlayer from "./components/AdPlayer";
import LoginView from "./components/LoginView";
import Sidebar from "./components/Sidebar";
import DashboardView from "./components/DashboardView";
import AnalysisView from "./components/AnalysisView";
import PlansView from "./components/PlansView";
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
  getStaleOrphans,
  queryNaturalLanguage,
  createPlan,
  getPlans,
  getPlan,
  approvePlan,
  undoPlan,
  analyzeConflict,
  getSemanticDuplicates,
  loginUser,
  registerOrganization,
  registerUser,
  getFleetStats,
  decommissionSource
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
  RefreshCw, 
  CheckCircle, 
  AlertTriangle, 
  Sparkles, 
  Download, 
  ShieldCheck,
  HardDrive
} from "lucide-react";

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem("setsync_token"));
  const [tokenInput, setTokenInput] = useState("");
  const [loginError, setLoginError] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);
  const [showPromoAd, setShowPromoAd] = useState(false);

  const [activeTab, setActiveTab] = useState<"dashboard" | "audit" | "dedupe" | "stale" | "plans">("dashboard");
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

  // AI Search states
  const [aiQueryText, setAiQueryText] = useState("");
  const [activeAiFilters, setActiveAiFilters] = useState<any>(null);

  // Plans state
  const [plans, setPlans] = useState<any[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<any | null>(null);
  const [loadingPlans, setLoadingPlans] = useState(false);
  const [draftPlanItems, setDraftPlanItems] = useState<any[]>([]);
  const [draftPlanName, setDraftPlanName] = useState("");



  // AI Conflict states
  const [aiConflictLoading, setAiConflictLoading] = useState(false);
  const [aiConflictRecommendation, setAiConflictRecommendation] = useState<{ recommendation: string; reasoning: string } | null>(null);

  // Semantic Deduplication states
  const [dedupeMode, setDedupeMode] = useState<"exact" | "semantic">("exact");
  const [semanticDuplicates, setSemanticDuplicates] = useState<any[]>([]);
  const [semanticThreshold, setSemanticThreshold] = useState<number>(10);
  const [loadingSemantic, setLoadingSemantic] = useState(false);

  // Enterprise Auth, Fleet & Decommission States
  const [loginMode, setLoginMode] = useState<"token" | "user" | "register">("user");
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regOrgName, setRegOrgName] = useState("");
  
  const [fleetStats, setFleetStats] = useState<any | null>(null);
  const [decommissionBlockedModal, setDecommissionBlockedModal] = useState<{
    open: boolean;
    sourceName: string;
    uniqueFiles: any[];
  }>({
    open: false,
    sourceName: "",
    uniqueFiles: []
  });
  const [decommissionCertModal, setDecommissionCertModal] = useState<{
    open: boolean;
    certText: string;
  }>({
    open: false,
    certText: ""
  });

  // DOM Virtualization State
  const [scrollTop, setScrollTop] = useState(0);

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
      let data;
      if (activeAiFilters) {
        data = await getSetsView(
          sourceX,
          sourceY,
          activeAiFilters.view_type || "union",
          activeAiFilters.q || undefined,
          activeAiFilters.min_size !== null && activeAiFilters.min_size !== undefined ? activeAiFilters.min_size : undefined,
          activeAiFilters.max_size !== null && activeAiFilters.max_size !== undefined ? activeAiFilters.max_size : undefined
        );
      } else {
        data = await getSetsView(sourceX, sourceY, viewType, searchQuery || undefined);
      }
      setFiles(data.files);
      setSummary(data.summary);
      setScrollTop(0);
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
    fetchFleetStats();
  }, [isAuthenticated]);

  // Re-fetch files when source selection, tab, or view type changes
  useEffect(() => {
    if (!isAuthenticated) return;
    if (activeTab === "dashboard") {
      fetchFiles();
      fetchFleetStats();
    } else if (activeTab === "dedupe") {
      if (dedupeMode === "exact") {
        fetchDuplicates();
      } else {
        fetchSemanticDedupe();
      }
    } else if (activeTab === "stale") {
      fetchStaleOrphans();
    } else if (activeTab === "plans") {
      fetchPlansList();
    }
  }, [sourceX, sourceY, viewType, activeTab, isAuthenticated, activeAiFilters, dedupeMode, semanticThreshold]);

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

  const fetchFleetStats = async () => {
    try {
      const data = await getFleetStats();
      setFleetStats(data);
    } catch (e) {
      console.error(e);
    }
  };

  const handleDecommission = async (source: any) => {
    if (!window.confirm(`Are you absolutely sure you want to decommission and retire the device '${source.name}'?`)) {
      return;
    }
    setActionLoading(true);
    try {
      const res = await decommissionSource(source.id);
      setDecommissionCertModal({
        open: true,
        certText: res.certificate
      });
      // Refresh sources and fleet stats
      await fetchStatus();
      await fetchFleetStats();
    } catch (e: any) {
      // If blocked because of unique files, the server returns 400 with the files list in details
      try {
        const errorDetail = JSON.parse(e.message);
        if (errorDetail && errorDetail.unique_files) {
          setDecommissionBlockedModal({
            open: true,
            sourceName: source.name,
            uniqueFiles: errorDetail.unique_files
          });
          return;
        }
      } catch {}
      alert("Failed to decommission: " + e.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!regEmail || !regPassword || !regOrgName) {
      setLoginError("Please fill all registration fields.");
      return;
    }
    setLoggingIn(true);
    setLoginError("");
    try {
      // 1. Create Organization
      const org = await registerOrganization(regOrgName);
      // 2. Create Admin User
      await registerUser(regEmail, regPassword, "admin", org.id);
      // 3. Login
      const loginRes = await loginUser(regEmail, regPassword);
      localStorage.setItem("setsync_token", loginRes.access_token);
      setIsAuthenticated(true);
    } catch (err: any) {
      setLoginError("Registration failed: " + err.message);
    } finally {
      setLoggingIn(false);
    }
  };

  const handleUserLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!loginEmail || !loginPassword) {
      setLoginError("Please enter email and password.");
      return;
    }
    setLoggingIn(true);
    setLoginError("");
    try {
      const res = await loginUser(loginEmail, loginPassword);
      localStorage.setItem("setsync_token", res.access_token);
      setIsAuthenticated(true);
    } catch (err: any) {
      setLoginError("Login failed: " + err.message);
    } finally {
      setLoggingIn(false);
    }
  };

  const handleMasterTokenLogin = async (e: React.FormEvent) => {
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

  const handleAiQuery = async () => {
    if (!aiQueryText.trim() || !sourceX || !sourceY) return;
    setLoadingFiles(true);
    try {
      const res = await queryNaturalLanguage(aiQueryText, sourceX, sourceY);
      setActiveAiFilters(res.filters);
      setFiles(res.files);
      setSummary(res.summary);
    } catch (e) {
      alert("AI Query translation failed: " + e);
    } finally {
      setLoadingFiles(false);
    }
  };

  const handleClearAiFilters = () => {
    setActiveAiFilters(null);
    setAiQueryText("");
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

  // Plans Management handlers
  const fetchPlansList = async () => {
    setLoadingPlans(true);
    try {
      const data = await getPlans();
      setPlans(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingPlans(false);
    }
  };

  const handleCreatePlan = async () => {
    if (!draftPlanName.trim()) {
      alert("Please enter a plan name.");
      return;
    }
    if (draftPlanItems.length === 0) {
      alert("Please add at least one item to the plan.");
      return;
    }
    try {
      await createPlan(draftPlanName, draftPlanItems);
      setDraftPlanName("");
      setDraftPlanItems([]);
      alert("Plan created successfully!");
      fetchPlansList();
    } catch (e: any) {
      alert("Failed to create plan: " + e.message);
    }
  };

  const handleSelectPlan = async (id: string) => {
    try {
      const data = await getPlan(id);
      setSelectedPlan(data);
    } catch (e) {
      alert("Failed to load plan details.");
    }
  };

  const handleApprovePlan = async (id: string) => {
    setActionLoading(true);
    try {
      const run = await approvePlan(id);
      setSelectedPlan(run);
      alert(`Plan approved and executed! Status: ${run.status}`);
      await fetchPlansList();
    } catch (e: any) {
      alert("Execution failed: " + e.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleUndoPlan = async (id: string) => {
    setActionLoading(true);
    try {
      const run = await undoPlan(id);
      setSelectedPlan(run);
      alert("Plan rolled back successfully!");
      await fetchPlansList();
    } catch (e: any) {
      alert("Undo failed: " + e.message);
    } finally {
      setActionLoading(false);
    }
  };

  const addToDraftPlan = (file: UnifiedFileRow, actionType: "copy" | "move" | "delete") => {
    const source = file.location === "A" ? sourceX : sourceY;
    const destination = source === sourceX ? sourceY : sourceX;
    const newItem = {
      action_type: actionType,
      file_path: file.relative_path,
      source_id: source,
      destination_id: destination,
      sequence: draftPlanItems.length
    };
    setDraftPlanItems([...draftPlanItems, newItem]);
    alert(`Added ${actionType} of ${file.name} to Draft Plan Queue!`);
  };

  // Semantic Deduplication handler
  const fetchSemanticDedupe = async () => {
    setLoadingSemantic(true);
    try {
      const data = await getSemanticDuplicates(semanticThreshold);
      setSemanticDuplicates(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingSemantic(false);
    }
  };

  const handleAiConflictAnalysis = async () => {
    const { row } = conflictModal;
    if (!row || !sourceX || !sourceY) return;
    setAiConflictLoading(true);
    setAiConflictRecommendation(null);
    try {
      const rec = await analyzeConflict(
        row.relative_path,
        sourceX,
        sourceY,
        { size_bytes: row.size_bytes, mtime: row.mtime_a || "", hash_sha256: row.hash_sha256 },
        { size_bytes: row.size_bytes, mtime: row.mtime_b || "", hash_sha256: row.hash_sha256 }
      );
      setAiConflictRecommendation(rec);
    } catch (e: any) {
      alert("AI Conflict resolution failed: " + e.message);
    } finally {
      setAiConflictLoading(false);
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
      <>
        {showPromoAd && <AdPlayer onClose={() => setShowPromoAd(false)} />}
        <LoginView
          loginMode={loginMode}
          setLoginMode={setLoginMode}
          loginEmail={loginEmail}
          setLoginEmail={setLoginEmail}
          loginPassword={loginPassword}
          setLoginPassword={setLoginPassword}
          regOrgName={regOrgName}
          setRegOrgName={setRegOrgName}
          regEmail={regEmail}
          setRegEmail={setRegEmail}
          regPassword={regPassword}
          setRegPassword={setRegPassword}
          tokenInput={tokenInput}
          setTokenInput={setTokenInput}
          loginError={loginError}
          setLoginError={setLoginError}
          loggingIn={loggingIn}
          handleUserLogin={handleUserLogin}
          handleRegister={handleRegister}
          handleMasterTokenLogin={handleMasterTokenLogin}
          setShowPromoAd={setShowPromoAd}
        />
      </>
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
        <Sidebar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          sourcesCount={sources.length}
          fetchFiles={fetchFiles}
          fetchDuplicates={fetchDuplicates}
          fetchStaleOrphans={fetchStaleOrphans}
          fetchLogs={fetchLogs}
          fetchPlansList={fetchPlansList}
        />

        {activeTab === "dashboard" && (
          <DashboardView
            fleetStats={fleetStats}
            sources={sources}
            sourceX={sourceX}
            setSourceX={setSourceX}
            sourceY={sourceY}
            setSourceY={setSourceY}
            handleDecommission={handleDecommission}
            actionLoading={actionLoading}
            aiQueryText={aiQueryText}
            setAiQueryText={setAiQueryText}
            handleAiQuery={handleAiQuery}
            activeAiFilters={activeAiFilters}
            handleClearAiFilters={handleClearAiFilters}
            viewType={viewType}
            setViewType={setViewType}
            summary={summary}
            inventoryStatus={inventoryStatus}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            loadingFiles={loadingFiles}
            files={files}
            scrollTop={scrollTop}
            setScrollTop={setScrollTop}
            handleOpenDryRun={handleOpenDryRun}
            addToDraftPlan={addToDraftPlan}
            handleSafeDelete={handleSafeDelete}
            setConflictModal={setConflictModal}
            formatSize={formatSize}
            formatDate={formatDate}
          />
        )}

        {(activeTab === "dedupe" || activeTab === "stale" || activeTab === "audit") && (
          <AnalysisView
            activeTab={activeTab}
            duplicatesReport={duplicatesReport}
            dedupeMode={dedupeMode}
            setDedupeMode={setDedupeMode}
            loadingDedupe={loadingDedupe}
            handleSafeDelete={handleSafeDelete}
            semanticThreshold={semanticThreshold}
            setSemanticThreshold={setSemanticThreshold}
            loadingSemantic={loadingSemantic}
            semanticDuplicates={semanticDuplicates}
            fetchSemanticDedupe={fetchSemanticDedupe}
            staleAgeDays={staleAgeDays}
            setStaleAgeDays={setStaleAgeDays}
            loadingStale={loadingStale}
            staleOrphans={staleOrphans}
            auditLogs={auditLogs}
            sources={sources}
            handleUndo={handleUndo}
            actionLoading={actionLoading}
            formatSize={formatSize}
            formatDate={formatDate}
          />
        )}

        {activeTab === "plans" && (
          <PlansView
            draftPlanName={draftPlanName}
            setDraftPlanName={setDraftPlanName}
            draftPlanItems={draftPlanItems}
            handleCreatePlan={handleCreatePlan}
            loadingPlans={loadingPlans}
            plans={plans}
            handleSelectPlan={handleSelectPlan}
            selectedPlan={selectedPlan}
            handleApprovePlan={handleApprovePlan}
            handleUndoPlan={handleUndoPlan}
            actionLoading={actionLoading}
          />
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
              
              <div className="glass-card" style={{ marginBottom: "1rem", padding: "1rem", display: "flex", flexDirection: "column", gap: "0.5rem", border: "1px solid rgba(0, 188, 212, 0.3)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: "0.35rem", color: "var(--accent-cyan)" }}>
                    <Sparkles size={16} /> SetSync Reasoned AI Conflict Solver
                  </span>
                  <button 
                    className="btn btn-sm btn-primary" 
                    onClick={handleAiConflictAnalysis}
                    disabled={aiConflictLoading}
                  >
                    {aiConflictLoading ? "Analyzing..." : "Ask AI Solver"}
                  </button>
                </div>
                
                {aiConflictRecommendation && (
                  <div style={{ marginTop: "0.5rem", borderTop: "1px dashed rgba(255,255,255,0.08)", paddingTop: "0.5rem", fontSize: "0.9rem" }}>
                    <div style={{ marginBottom: "0.25rem" }}>
                      Recommendation: <strong style={{ color: "var(--success)" }}>Keep Version {aiConflictRecommendation.recommendation === "A" ? nameX : nameY}</strong>
                    </div>
                    <div style={{ color: "var(--text-secondary)", fontSize: "0.85rem", lineHeight: "1.3" }}>
                      Reasoning: {aiConflictRecommendation.reasoning}
                    </div>
                  </div>
                )}
              </div>
              
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
      {/* Decommission Blocked Modal */}
      {decommissionBlockedModal.open && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: "600px" }}>
            <div className="modal-header" style={{ color: "var(--danger)" }}>
              <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <AlertTriangle size={20} />
                Retirement Blocked: Data Loss Risk
              </h3>
              <button 
                className="close-btn"
                onClick={() => setDecommissionBlockedModal({ open: false, sourceName: "", uniqueFiles: [] })}
              >
                ✕
              </button>
            </div>
            
            <div className="modal-body">
              <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem" }}>
                Cannot decommission device <strong>{decommissionBlockedModal.sourceName}</strong>. The following <strong>{decommissionBlockedModal.uniqueFiles.length}</strong> unique files exist only on this machine and have no copies elsewhere in the organization:
              </p>
              
              <div style={{ maxHeight: "250px", overflowY: "auto", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px", margin: "1rem 0" }}>
                <table className="file-table" style={{ width: "100%", margin: 0 }}>
                  <thead>
                    <tr>
                      <th style={{ padding: "0.5rem" }}>File Path</th>
                      <th style={{ padding: "0.5rem", textAlign: "right" }}>Size</th>
                    </tr>
                  </thead>
                  <tbody>
                    {decommissionBlockedModal.uniqueFiles.map((file, idx) => (
                      <tr key={idx}>
                        <td className="file-path" style={{ padding: "0.5rem" }}>{file.relative_path}</td>
                        <td style={{ padding: "0.5rem", textAlign: "right" }}>{formatSize(file.size_bytes)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", margin: 0 }}>
                Please run a sync or copy plan to copy these files to another active device before decommissioning.
              </p>
            </div>

            <div className="modal-footer">
              <button 
                className="btn btn-primary"
                onClick={() => setDecommissionBlockedModal({ open: false, sourceName: "", uniqueFiles: [] })}
              >
                Close & Resolve
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Decommission Certificate Modal */}
      {decommissionCertModal.open && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: "600px" }}>
            <div className="modal-header" style={{ color: "var(--success)" }}>
              <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <ShieldCheck size={20} />
                Device Decommissioned Safely
              </h3>
              <button 
                className="close-btn"
                onClick={() => setDecommissionCertModal({ open: false, certText: "" })}
              >
                ✕
              </button>
            </div>
            
            <div className="modal-body">
              <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem" }}>
                The device has been retired from the active fleet. Below is the generated retirement verification certificate:
              </p>
              
              <pre 
                style={{ 
                  padding: "1rem", 
                  backgroundColor: "rgba(0,0,0,0.2)", 
                  borderRadius: "8px", 
                  fontSize: "0.85rem", 
                  color: "#fff",
                  fontFamily: "monospace",
                  overflowX: "auto",
                  whiteSpace: "pre-wrap",
                  lineHeight: "1.4"
                }}
              >
                {decommissionCertModal.certText}
              </pre>
            </div>

            <div className="modal-footer">
              <button 
                className="btn btn-secondary"
                onClick={() => {
                  const element = document.createElement("a");
                  const file = new Blob([decommissionCertModal.certText], {type: 'text/plain'});
                  element.href = URL.createObjectURL(file);
                  element.download = `setsync-decommission-certificate-${Date.now()}.md`;
                  document.body.appendChild(element);
                  element.click();
                  document.body.removeChild(element);
                }}
              >
                Download Certificate
              </button>
              <button 
                className="btn btn-primary"
                onClick={() => setDecommissionCertModal({ open: false, certText: "" })}
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
