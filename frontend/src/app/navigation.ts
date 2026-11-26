
import type { LucideIcon } from "lucide-react";

import {
  Activity,
  BrainCircuit,
  CalendarDays,
  FileText,
  LayoutDashboard,
  MessageSquare,
  NotebookPen,
  Search,
  Sparkles,
  Workflow,
} from "lucide-react";

import type { Page } from "../types/navigation";

export interface NavigationItem {
  label: Page;
  icon: LucideIcon;
  section: string;
  available: boolean;
}

export const navigation: NavigationItem[] = [
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

export const navigationSections = [
  "WORKSPACE",
  "COMING NEXT",
];
