
import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import {
  Activity,
  ArrowRight,
  Bot,
  BrainCircuit,
  CalendarDays,
  Check,
  ChevronDown,
  CircleHelp,
  Clock3,
  FileText,
  LayoutDashboard,
  MessageSquare,
  NotebookPen,
  Search,
  Settings,
  Sparkles,
  Workflow,
  Menu,
  X,
} from "lucide-react";

type Page =
  | "Dashboard"
  | "Chat"
  | "Notes"
  | "Search"
  | "Activity"
  | "Memory"
  | "Research"
  | "Reminders"
  | "Documents"
  | "Automation"
  | "Settings";

type BackendStatus = "checking" | "online" | "offline";

const navigation: {
  label: Page;
  icon: typeof LayoutDashboard;
  section: string;
  available: boolean;
}[] = [
  {
    label: "Dashboard",
    icon: LayoutDashboard,
    section: "WORKSPACE",
    available: true,
  },
  {
    label: "Chat",
    icon: MessageSquare,
    section: "WORKSPACE",
    available: true,
  },
  {
    label: "Notes",
    icon: NotebookPen,
    section: "WORKSPACE",
    available: true,
  },
  {
    label: "Search",
    icon: Search,
    section: "WORKSPACE",
    available: true,
  },
  {
    label: "Activity",
    icon: Activity,
    section: "WORKSPACE",
    available: true,
  },
  {
    label: "Memory",
    icon: BrainCircuit,
    section: "COMING NEXT",
    available: false,
  },
  {
    label: "Research",
    icon: Sparkles,
    section: "COMING NEXT",
    available: false,
  },
  {
    label: "Reminders",
    icon: CalendarDays,
    section: "COMING NEXT",
    available: false,
  },
  {
    label: "Documents",
    icon: FileText,
    section: "COMING NEXT",
    available: false,
  },
  {
    label: "Automation",
    icon: Workflow,
    section: "COMING NEXT",
    available: false,
  },
];

function App() {
  const [activePage, setActivePage] =
    useState<Page>("Dashboard");

  const [backendStatus, setBackendStatus] =
    useState<BackendStatus>("checking");

  const [sidebarOpen, setSidebarOpen] =
    useState(false);

  useEffect(() => {
    let mounted = true;

    async function checkBackend() {
      try {
        const response = await fetch(
          "http://127.0.0.1:8000/api/health"
        );

        if (!response.ok) {
          throw new Error("Backend unavailable");
        }

        if (mounted) {
          setBackendStatus("online");
        }
      } catch {
        if (mounted) {
          setBackendStatus("offline");
        }
      }
    }

    checkBackend();

    return () => {
      mounted = false;
    };
  }, []);

  function navigate(page: Page) {
    setActivePage(page);
    setSidebarOpen(false);
  }

  const sections = [
    "WORKSPACE",
    "COMING NEXT",
  ];

  return (
    <div className="app-shell">

      {sidebarOpen && (
        <div
          className="mobile-overlay"
          onClick={() => setSidebarOpen(false)}
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
            onClick={() => setSidebarOpen(false)}
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

          {sections.map((section) => {
            const items = navigation.filter(
              (item) => item.section === section
            );

            return (
              <div className="nav-section" key={section}>

                <p className="nav-heading">
                  {section}
                </p>

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

      <main className="main-area">

        <header className="topbar">

          <div className="topbar-left">

            <button
              className="mobile-menu"
              onClick={() => setSidebarOpen(true)}
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

            <div
              className={`backend-status ${
                backendStatus
              }`}
            >
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

            <div className="topbar-avatar">
              JH
            </div>

          </div>

        </header>

        <div className="page-content">

          {activePage === "Dashboard" ? (
            <Dashboard
              backendStatus={backendStatus}
              navigate={navigate}
            />
          ) : (
            <WorkspacePlaceholder
              page={activePage}
              navigate={navigate}
            />
          )}

        </div>

      </main>

    </div>
  );
}

function Dashboard({
  backendStatus,
  navigate,
}: {
  backendStatus: BackendStatus;
  navigate: (page: Page) => void;
}) {
  return (
    <div className="dashboard">

      <section className="welcome-section">

        <div>
          <div className="eyebrow">
            <Sparkles size={15} />
            YOUR PERSONAL AI WORKSPACE
          </div>

          <h2>
            Good to see you again.
          </h2>

          <p>
            Your workspace is ready. What would you
            like to accomplish today?
          </p>
        </div>

        <div className="welcome-decoration">
          <div className="decoration-circle circle-one" />
          <div className="decoration-circle circle-two" />
          <BrainCircuit size={66} strokeWidth={1.2} />
        </div>

      </section>

      <section className="assistant-card">

        <div className="assistant-icon">
          <Bot size={27} />
        </div>

        <div className="assistant-content">

          <div className="assistant-title-row">
            <h3>Your PPA assistant</h3>
            <span className="agent-badge">
              <span />
              Agent ready
            </span>
          </div>

          <p>
            I can help you organize your notes, find
            information, and work through your tasks.
            What would you like to do?
          </p>

          <button
            className="primary-button"
            onClick={() => navigate("Chat")}
          >
            Start a conversation
            <ArrowRight size={17} />
          </button>

        </div>

        <div className="assistant-decoration">
          <Sparkles size={25} />
        </div>

      </section>

      <section className="section-block">

        <div className="section-heading">
          <div>
            <h3>Workspace overview</h3>
            <p>Your currently available capabilities</p>
          </div>
        </div>

        <div className="capability-grid">

          <CapabilityCard
            icon={<MessageSquare />}
            title="AI Chat"
            description="Talk with your personal AI agent."
            status="Interface available"
            onClick={() => navigate("Chat")}
          />

          <CapabilityCard
            icon={<NotebookPen />}
            title="Notes"
            description="Create, update and organize notes."
            status="Backend implemented"
            onClick={() => navigate("Notes")}
          />

          <CapabilityCard
            icon={<Search />}
            title="Search"
            description="Find information in your notes."
            status="Backend implemented"
            onClick={() => navigate("Search")}
          />

          <CapabilityCard
            icon={<Activity />}
            title="Activity"
            description="Explore your agent's operations."
            status="Coming soon"
            onClick={() => navigate("Activity")}
          />

        </div>

      </section>

      <section className="section-block">

        <div className="section-heading">
          <div>
            <h3>System status</h3>
            <p>Current application infrastructure</p>
          </div>
        </div>

        <div className="system-card">

          <div className="system-item">
            <div className="system-icon">
              <Bot size={20} />
            </div>

            <div>
              <strong>FastAPI backend</strong>
              <span>Application API</span>
            </div>

            <span className={`system-state ${backendStatus}`}>
              {backendStatus === "online"
                ? "Connected"
                : backendStatus === "offline"
                ? "Unavailable"
                : "Checking"}
            </span>
          </div>

          <div className="system-divider" />

          <div className="system-item">
            <div className="system-icon database-icon">
              <Check size={20} />
            </div>

            <div>
              <strong>PostgreSQL</strong>
              <span>Existing persistence layer</span>
            </div>

            <span className="system-state planned">
              Existing setup
            </span>
          </div>

          <div className="system-divider" />

          <div className="system-item">
            <div className="system-icon agent-icon">
              <BrainCircuit size={20} />
            </div>

            <div>
              <strong>Agent engine</strong>
              <span>Existing Python implementation</span>
            </div>

            <span className="system-state planned">
              CLI available
            </span>
          </div>

        </div>

      </section>

      <section className="future-banner">
        <div className="future-icon">
          <Sparkles size={22} />
        </div>

        <div>
          <strong>Building a more capable assistant</strong>
          <p>
            Memory, research, reminders and workflow
            automation will join this workspace as
            we develop them.
          </p>
        </div>

        <ArrowRight size={19} />
      </section>

    </div>
  );
}

function CapabilityCard({
  icon,
  title,
  description,
  status,
  onClick,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  status: string;
  onClick: () => void;
}) {
  return (
    <button
      className="capability-card"
      onClick={onClick}
    >
      <div className="capability-icon">
        {icon}
      </div>

      <div className="capability-card-content">
        <h4>{title}</h4>
        <p>{description}</p>
      </div>

      <span className="capability-status">
        {status}
      </span>
    </button>
  );
}

function WorkspacePlaceholder({
  page,
  navigate,
}: {
  page: Page;
  navigate: (page: Page) => void;
}) {
  const descriptions: Record<Page, string> = {
    Dashboard: "",
    Chat: "Your conversational interface will connect to the existing PPA agent in our next milestone.",
    Notes: "The Notes Management interface will connect to our existing PostgreSQL-backed Notes services.",
    Search: "Search across your saved notes will be available here.",
    Activity: "A detailed view of agent executions, tool calls and operation history will be developed here.",
    Memory: "Persistent personal memory and contextual retrieval.",
    Research: "An intelligent research workspace for papers, sources and findings.",
    Reminders: "Scheduled reminders and recurring notifications.",
    Documents: "Upload, search and ask questions about your documents.",
    Automation: "Create workflows that combine tools and actions.",
    Settings: "Application and agent configuration.",
  };

  const isFuture = [
    "Memory",
    "Research",
    "Reminders",
    "Documents",
    "Automation",
  ].includes(page);

  return (
    <div className="placeholder-page">

      <div className="placeholder-icon">
        <Sparkles size={30} />
      </div>

      <span className="eyebrow">
        {isFuture ? "COMING IN A FUTURE MILESTONE" : "WORKSPACE"}
      </span>

      <h2>{page}</h2>

      <p>{descriptions[page]}</p>

      {isFuture ? (
        <span className="future-pill">
          Planned capability
        </span>
      ) : (
        <button
          className="primary-button"
          onClick={() => navigate("Dashboard")}
        >
          Back to dashboard
          <ArrowRight size={17} />
        </button>
      )}

    </div>
  );
}

export default App;
