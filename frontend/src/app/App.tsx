import { useState } from "react";

import Sidebar from "../components/layout/Sidebar";
import Topbar from "../components/layout/Topbar";

import DashboardPage from "../features/dashboard/DashboardPage";
import ChatPage from "../features/chat/ChatPage";

import WorkspacePlaceholder from "../components/common/WorkspacePlaceholder";

import { useBackendHealth } from "../hooks/useBackendHealth";

import type { Page } from "../types/navigation";

import "../styles/layout.css";
import "../styles/chat.css";

export default function App() {
  const [activePage, setActivePage] =
    useState<Page>("Dashboard");

  const [sidebarOpen, setSidebarOpen] =
    useState(false);

  const backendStatus = useBackendHealth();

  function navigate(page: Page) {
    setActivePage(page);
    setSidebarOpen(false);
  }

  function renderPage() {
    switch (activePage) {
      case "Dashboard":
        return (
          <DashboardPage
            backendStatus={backendStatus}
            navigate={navigate}
          />
        );

      case "Chat":
        return <ChatPage />;

      default:
        return (
          <WorkspacePlaceholder
            page={activePage}
            navigate={navigate}
          />
        );
    }
  }

  return (
    <div className="app-shell">
      <Sidebar
        activePage={activePage}
        navigate={navigate}
        sidebarOpen={sidebarOpen}
        closeSidebar={() => setSidebarOpen(false)}
      />

      <main className="main-area">
        <Topbar
          activePage={activePage}
          backendStatus={backendStatus}
          navigate={navigate}
          openSidebar={() => setSidebarOpen(true)}
        />

        <div className="page-content">
          {renderPage()}
        </div>
      </main>
    </div>
  );
}
