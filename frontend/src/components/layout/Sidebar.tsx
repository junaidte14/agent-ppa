import {
  BrainCircuit,
  ChevronDown,
  CircleHelp,
  Settings,
  X,
} from "lucide-react";

import { navigation, navigationSections } from "../../app/navigation";
import type { Navigate, Page } from "../../types/navigation";

interface SidebarProps {
  activePage: Page;
  navigate: Navigate;
  sidebarOpen: boolean;
  closeSidebar: () => void;
}

export default function Sidebar({
  activePage,
  navigate,
  sidebarOpen,
  closeSidebar,
}: SidebarProps) {
  return (
    <>
      {sidebarOpen && (
        <div
          className="mobile-overlay"
          onClick={closeSidebar}
        />
      )}

      <aside
        className={`sidebar ${
          sidebarOpen ? "sidebar-open" : ""
        }`}
      >
        <div className="brand">
          <div className="brand-icon">
            <BrainCircuit size={25} />
          </div>

          <div className="brand-copy">
            <h1>PPA</h1>
            <span>Personal AI Workspace</span>
          </div>

          <button
            className="mobile-close"
            onClick={closeSidebar}
            aria-label="Close navigation"
          >
            <X size={19} />
          </button>
        </div>

        <button className="workspace-selector">
          <div className="workspace-avatar">J</div>

          <div className="workspace-copy">
            <strong>My Workspace</strong>
            <span>Personal account</span>
          </div>

          <ChevronDown size={16} />
        </button>

        <nav className="navigation">
          {navigationSections.map((section) => {
            const items = navigation.filter(
              (item) => item.section === section,
            );

            return (
              <div className="nav-section" key={section}>
                <p className="nav-heading">{section}</p>

                {items.map((item) => {
                  const Icon = item.icon;

                  return (
                    <button
                      key={item.label}
                      className={`nav-item ${
                        activePage === item.label
                          ? "nav-item-active"
                          : ""
                      } ${
                        !item.available
                          ? "nav-item-disabled"
                          : ""
                      }`}
                      onClick={() => {
                        if (item.available) {
                          navigate(item.label);
                        }
                      }}
                      disabled={!item.available}
                    >
                      <Icon size={18} />

                      <span>{item.label}</span>

                      {!item.available && (
                        <span className="coming-dot" />
                      )}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </nav>

        <div className="sidebar-bottom">
          <div className="help-card">
            <div className="help-icon">
              <CircleHelp size={19} />
            </div>

            <strong>Need assistance?</strong>

            <span>
              Your personal assistant is here to help.
            </span>
          </div>

          <button
            className={`nav-item ${
              activePage === "Settings"
                ? "nav-item-active"
                : ""
            }`}
            onClick={() => navigate("Settings")}
          >
            <Settings size={18} />
            <span>Settings</span>
          </button>

          <div className="sidebar-footer">
            <div className="user-avatar">JH</div>

            <div className="user-copy">
              <strong>My Account</strong>
              <span>PPA workspace</span>
            </div>

            <ChevronDown size={16} />
          </div>
        </div>
      </aside>
    </>
  );
}
