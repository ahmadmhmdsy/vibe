// components/ui/SearchField.tsx — a labelled search input with a clear button.
import { forwardRef, useId, type InputHTMLAttributes } from "react";
import { Icon } from "../icons/Icon";
import { IconButton } from "./IconButton";

export interface SearchFieldProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "type" | "value" | "onChange"
> {
  value: string;
  onValueChange: (value: string) => void;
  /** Accessible name. Visually hidden, because the magnifier and placeholder
   *  already say what the field is — but a screen reader needs the real one. */
  label: string;
  placeholder?: string;
}

export const SearchField = forwardRef<HTMLInputElement, SearchFieldProps>(function SearchField(
  { value, onValueChange, label, placeholder = "Search…", className, id, ...rest },
  ref
) {
  const generatedId = useId();
  const inputId = id ?? `search-${generatedId}`;

  return (
    <div className={["search-field", className].filter(Boolean).join(" ")}>
      <Icon name="search" size={14} />
      <label className="sr-only" htmlFor={inputId}>
        {label}
      </label>
      <input
        ref={ref}
        id={inputId}
        type="search"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onValueChange(event.target.value)}
        {...rest}
      />
      {value ? (
        <IconButton
          className="search-field-clear"
          label={`Clear ${label.toLowerCase()}`}
          onClick={() => onValueChange("")}
        >
          <Icon name="close" size={12} />
        </IconButton>
      ) : null}
    </div>
  );
});
