import "../../styles/dashboard.css";
import {
  Activity,
  ArrowRight,
  Bot,
  BrainCircuit,
  Check,
  MessageSquare,
  NotebookPen,
  Search,
  Sparkles,
} from "lucide-react";

import CapabilityCard from "../../components/common/CapabilityCard";
import type { BackendStatus } from "../../hooks/useBackendHealth";
import type { Navigate } from "../../types/navigation";

interface DashboardPageProps {
  backendStatus: BackendStatus;
  navigate: Navigate;
}

export default function DashboardPage({
  backendStatus,
  navigate,
}: DashboardPageProps) {
  return (
    <div className="dashboard">
      <section className="welcome-section">
        <div>
          <div className="eyebrow">
            <Sparkles size={15} />
            YOUR PERSONAL AI WORKSPACE
          </div>

          <h2>Good to see you again.</h2>

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
