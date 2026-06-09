import { useId, useRef } from "react";

export default function FilePicker({
  accept,
  multiple = false,
  label = "Choose file…",
  files = null,
  onChange,
  disabled = false,
}) {
  const inputRef = useRef(null);
  const id = useId();

  let summary = label;
  if (multiple && files?.length) {
    summary = files.length === 1 ? files[0].name : `${files.length} files selected`;
  } else if (!multiple && files?.name) {
    summary = files.name;
  }

  return (
    <div className="file-picker">
      <input
        ref={inputRef}
        id={id}
        type="file"
        accept={accept}
        multiple={multiple}
        disabled={disabled}
        onChange={(e) => {
          if (multiple) onChange([...(e.target.files || [])]);
          else onChange(e.target.files?.[0] || null);
          e.target.value = "";
        }}
      />
      <label htmlFor={id} className={`file-label util-file-label${disabled ? " disabled" : ""}`}>
        📎 {summary}
      </label>
    </div>
  );
}
