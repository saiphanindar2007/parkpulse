const TAG_STYLES = {
  HIGH: { color: "#22c55e", label: "HIGH" },
  MEDIUM: { color: "#f59e0b", label: "MED" },
  LOW: { color: "#dc2626", label: "LOW" },
};

export default function ConfidenceTag({ tag, explanation }) {
  if (!tag) return null;
  const style = TAG_STYLES[tag] || TAG_STYLES.LOW;

  return (
    <span
      className="confidence-tag"
      style={{ color: style.color, borderColor: style.color }}
      title={explanation || ""}
    >
      {style.label}
    </span>
  );
}