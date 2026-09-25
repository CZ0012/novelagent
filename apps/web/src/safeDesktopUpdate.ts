type UpdateSteps = {
  download: () => Promise<void>;
  confirmSaved: () => Promise<boolean>;
  prepare: () => Promise<void>;
  install: () => Promise<void>;
  cancel: () => Promise<void>;
  restoreManagedBackend: (() => Promise<void>) | null;
};

export class DesktopUpdateFailure extends Error {
  constructor(
    readonly stage: "download" | "preparation" | "installation",
    readonly cause: unknown,
    readonly recovery: "not_needed" | "external_untouched" | "restored" | "restore_failed" | "cancel_failed",
    readonly recoveryError?: unknown
  ) {
    super("Desktop update failed");
    this.name = "DesktopUpdateFailure";
  }

  get canRetry(): boolean {
    return this.recovery !== "restore_failed" && this.recovery !== "cancel_failed";
  }
}

/** Rust preserves the Windows sharing/lock error code in its original cause.
 * Other preparation failures must not be described as a file being in use. */
export function isWindowsUpdateFileLock(cause: unknown): boolean {
  const message = cause instanceof Error ? cause.message : typeof cause === "string" ? cause : "";
  return /\bos error (?:32|33)\b/i.test(message);
}

/** Download keeps the backend alive. Installation starts only after edits and
 * native process/file readiness checks have both succeeded. */
export async function runSafeDesktopUpdate(steps: UpdateSteps): Promise<"installed" | "cancelled"> {
  try { await steps.download(); }
  catch (error) { throw new DesktopUpdateFailure("download", error, "not_needed"); }
  if (!await steps.confirmSaved()) return "cancelled";
  let stage: DesktopUpdateFailure["stage"] = "preparation";
  try {
    await steps.prepare();
    stage = "installation";
    await steps.install();
    return "installed";
  } catch (error) {
    // Prepare may stop the child before a later readiness check fails. Always
    // release the native update gate before any managed backend restoration.
    try { await steps.cancel(); }
    catch (cancelError) { throw new DesktopUpdateFailure(stage, error, "cancel_failed", cancelError); }
    if (!steps.restoreManagedBackend) throw new DesktopUpdateFailure(stage, error, "external_untouched");
    try { await steps.restoreManagedBackend(); }
    catch (restoreError) { throw new DesktopUpdateFailure(stage, error, "restore_failed", restoreError); }
    throw new DesktopUpdateFailure(stage, error, "restored");
  }
}
