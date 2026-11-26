import { Clock3, Menu } from "lucide-react";

import type { BackendStatus } from "../../hooks/useBackendHealth";
import type { Navigate, Page } from "../../types/navigation";

interface TopbarProps {
  activePage: Page;
  backendStatus: BackendStatus;
  navigate: Navigate;
  openSidebar: () => void;
}

export default function Topbar({
  activePage,
  backendStatus,
  navigate,
  openSidebar,
}: TopbarProps) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          className="mobile-menu"
          onClick={openSidebar}
          aria-label="Open navigation"
        >
          <Menu size={21} />
        </button>

        <div className="breadcrumb">
          <span>Workspace</span>
          <span className="breadcrumb-divider">/</span>
          <strong>{activePage}</strong>
        </div>
      </div>

      <div className="topbar-right">
        <div className={`backend-status ${backendStatus}`}>
          <span className="status-dot" />

          {backendStatus === "checking"
            ? "Connecting"
            : backendStatus === "online"
              ? "Backend online"
              : "Backend offline"}
        </div>

        <button
          className="icon-button"
          title="Activity"
          onClick={() => navigate("Activity")}
        >
          <Clock3 size={19} />
        </button>

        <div className="topbar-avatar">JH</div>
      </div>
    </header>
  );
}
