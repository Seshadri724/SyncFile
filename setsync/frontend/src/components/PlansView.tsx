import { CheckCircle, Undo } from "lucide-react";

interface PlansViewProps {
  draftPlanName: string;
  setDraftPlanName: (name: string) => void;
  draftPlanItems: any[];
  handleCreatePlan: () => void;
  loadingPlans: boolean;
  plans: any[];
  handleSelectPlan: (id: string) => void;
  selectedPlan: any | null;
  handleApprovePlan: (id: string) => void;
  handleUndoPlan: (id: string) => void;
  actionLoading: boolean;
}

export default function PlansView({
  draftPlanName,
  setDraftPlanName,
  draftPlanItems,
  handleCreatePlan,
  loadingPlans,
  plans,
  handleSelectPlan,
  selectedPlan,
  handleApprovePlan,
  handleUndoPlan,
  actionLoading
}: PlansViewProps) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: "1.5rem" }}>
      {/* Left side: List of plans + Create Plan */}
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <section className="glass-card" style={{ gap: "1rem" }}>
          <h3 style={{ margin: 0, fontSize: "1.1rem" }}>Create New Transaction Plan</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <input
              type="text"
              className="search-input"
              placeholder="Plan Name (e.g. PC-A Sync Plan)"
              value={draftPlanName}
              onChange={(e) => setDraftPlanName(e.target.value)}
              style={{ width: "100%", height: "40px", borderRadius: "8px", paddingLeft: "0.75rem" }}
            />
            <div style={{ border: "1px dashed rgba(255,255,255,0.08)", borderRadius: "8px", padding: "0.75rem", minHeight: "80px", backgroundColor: "rgba(0,0,0,0.1)" }}>
              <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.5rem" }}>Draft Queue ({draftPlanItems.length} items):</div>
              {draftPlanItems.length === 0 ? (
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Use "Add to Plan" button (+ Plan) on Dashboard files to queue copy/move steps.</span>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem", maxHeight: "150px", overflowY: "auto" }}>
                  {draftPlanItems.map((item, idx) => (
                    <div key={idx} style={{ fontSize: "0.8rem", display: "flex", justifyContent: "space-between", backgroundColor: "rgba(255,255,255,0.03)", padding: "0.25rem 0.5rem", borderRadius: "4px" }}>
                      <span className="file-path" style={{ maxWidth: "200px" }}>{item.file_path}</span>
                      <span style={{ color: "var(--accent-cyan)", fontWeight: 600 }}>{item.action_type.toUpperCase()}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <button
              className="btn btn-primary"
              onClick={handleCreatePlan}
              disabled={draftPlanItems.length === 0 || !draftPlanName.trim()}
              style={{ width: "100%", height: "40px", borderRadius: "8px", fontWeight: "600" }}
            >
              Save Draft Plan
            </button>
          </div>
        </section>

        <section className="glass-card" style={{ gap: "1rem" }}>
          <h3 style={{ margin: 0, fontSize: "1.1rem" }}>Saved Execution Plans</h3>
          {loadingPlans ? (
            <div style={{ textAlign: "center", color: "var(--text-muted)" }}>Loading plans...</div>
          ) : plans.length === 0 ? (
            <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", textAlign: "center", padding: "1rem" }}>No saved plans.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {plans.map(p => (
                <div
                  key={p.id}
                  onClick={() => handleSelectPlan(p.id)}
                  style={{
                    padding: "1rem",
                    borderRadius: "8px",
                    cursor: "pointer",
                    border: selectedPlan?.id === p.id ? "1px solid var(--accent-cyan)" : "1px solid transparent",
                    backgroundColor: selectedPlan?.id === p.id ? "rgba(0,188,212,0.05)" : "rgba(255,255,255,0.02)"
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <strong style={{ fontSize: "0.95rem" }}>{p.name}</strong>
                    <span className={`audit-status ${p.status.toLowerCase()}`}>{p.status}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.5rem" }}>
                    <span>Items: {p.items.length}</span>
                    <span>{new Date(p.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Right side: Plan Details & Actions */}
      <div>
        {selectedPlan ? (
          <section className="glass-card" style={{ gap: "1.25rem", height: "100%" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: "0.75rem" }}>
              <div>
                <h3 style={{ margin: 0, fontSize: "1.25rem" }}>{selectedPlan.name}</h3>
                <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>ID: {selectedPlan.id}</span>
              </div>
              <span className={`audit-status ${selectedPlan.status.toLowerCase()}`} style={{ fontSize: "0.9rem" }}>{selectedPlan.status.toUpperCase()}</span>
            </div>

            <div style={{ display: "flex", gap: "0.75rem" }}>
              {(selectedPlan.status === "draft" || selectedPlan.status === "failed") && (
                <button
                  className="btn btn-primary"
                  style={{ flex: 1, height: "42px", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.35rem" }}
                  onClick={() => handleApprovePlan(selectedPlan.id)}
                  disabled={actionLoading}
                >
                  <CheckCircle size={16} /> Approve & Run Plan
                </button>
              )}
              {(selectedPlan.status === "completed" || selectedPlan.status === "failed") && (
                <button
                  className="btn btn-danger"
                  style={{ flex: 1, height: "42px", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.35rem" }}
                  onClick={() => handleUndoPlan(selectedPlan.id)}
                  disabled={actionLoading}
                >
                  <Undo size={16} /> Rollback/Undo Plan
                </button>
              )}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", maxHeight: "400px", overflowY: "auto" }}>
              <h4 style={{ margin: 0, fontSize: "0.95rem", color: "var(--text-secondary)" }}>Plan Execution Steps:</h4>
              {selectedPlan.items.map((item: any, idx: number) => (
                <div
                  key={item.id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "0.75rem 1rem",
                    borderRadius: "8px",
                    backgroundColor: "rgba(255,255,255,0.015)"
                  }}
                >
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Step {idx + 1}</span>
                    <strong style={{ fontSize: "0.9rem" }} className="file-path">{item.file_path}</strong>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Action: {item.action_type.toUpperCase()}</span>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <span className={`audit-status ${item.status.toLowerCase()}`}>{item.status}</span>
                    {item.error_message && (
                      <div style={{ color: "var(--danger)", fontSize: "0.75rem", marginTop: "0.25rem" }}>{item.error_message}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : (
          <section className="glass-card" style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "300px", color: "var(--text-muted)" }}>
            Select a plan on the left to inspect configuration, logs, and trigger transactions.
          </section>
        )}
      </div>
    </div>
  );
}
