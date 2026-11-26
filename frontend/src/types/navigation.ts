
export type Page =
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

export type Navigate = (page: Page) => void;
