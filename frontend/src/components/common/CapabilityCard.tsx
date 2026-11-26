import type { ReactNode } from "react";

interface CapabilityCardProps {
  icon: ReactNode;
  title: string;
  description: string;
  status: string;
  onClick: () => void;
}

export default function CapabilityCard({
  icon,
  title,
  description,
  status,
  onClick,
}: CapabilityCardProps) {
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
