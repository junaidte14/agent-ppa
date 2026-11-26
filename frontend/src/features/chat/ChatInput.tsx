import { useState, type SubmitEvent } from "react";
import { Send } from "lucide-react";

interface Props {
  onSend: (message: string) => void;
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: Props) {
  const [message, setMessage] = useState("");

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedMessage = message.trim();

    if (!trimmedMessage || disabled) {
      return;
    }

    onSend(trimmedMessage);
    setMessage("");
  }

  return (
    <form className="chat-input-form" onSubmit={handleSubmit}>
      <textarea
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        placeholder="Message your assistant..."
        rows={2}
        maxLength={4000}
        disabled={disabled}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            event.currentTarget.form?.requestSubmit();
          }
        }}
      />

      <button
        type="submit"
        disabled={disabled || !message.trim()}
        aria-label="Send message"
      >
        {disabled ? "Thinking..." : <Send size={18} />}
      </button>
    </form>
  );
}