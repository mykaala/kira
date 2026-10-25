import type { ButtonHTMLAttributes } from "react";
import styles from "./Button.module.css";

export type ButtonVariant = "lantern" | "coral" | "teal" | "surface" | "ghost" | "dark";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "small" | "medium" | "large";
  block?: boolean;
};

/** Chunky button with a hard offset shadow that grows on hover. */
export function Button({ variant = "surface", size = "medium", block, className, type = "button", ...rest }: Props) {
  const cls = [styles.button, styles[variant], size !== "medium" && styles[size], block && styles.block, className]
    .filter(Boolean)
    .join(" ");
  return <button type={type} className={cls} {...rest} />;
}
