
import { ArrowRight, Sparkles } from "lucide-react";

import type { Navigate, Page } from "../../types/navigation";

interface WorkspacePlaceholderProps {
  page: Page;
  navigate: Navigate;
}

const descriptions: Record<Page, string> = {
  Dashboard: "",
  Chat: "Your conversational interface connects to the existing PPA agent.",
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

const futurePages: Page[] = [
  "Memory",
  "Research",
  "Reminders",
  "Documents",
  "Automation",
];

export default function WorkspacePlaceholder({
  page,
  navigate,
}: WorkspacePlaceholderProps) {
  const isFuture = futurePages.includes(page);

  return (
    <div className="placeholder-page">
      <div className="placeholder-icon">
        <Sparkles size={30} />
      </div>

      <span className="eyebrow">
        {isFuture
          ? "COMING IN A FUTURE MILESTONE"
          : "WORKSPACE"}
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
