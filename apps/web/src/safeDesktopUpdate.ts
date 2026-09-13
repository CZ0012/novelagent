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
    readonly cause: unknown,
    readonly recovery: "not_needed" | "external_untouched" | "restored" | "restore_failed" | "cancel_failed",
    readonly recoveryError?: unknown
  ) {
    super("Desktop update failed");
    this.name = "DesktopUpdateFailure";
  }
}

/** Download keeps the backend alive. Installation starts only after edits and
 * native process/file readiness checks have both succeeded. */
export async function runSafeDesktopUpdate(steps: UpdateSteps): Promise<"installed" | "cancelled"> {
  try { await steps.download(); }
  catch (error) { throw new DesktopUpdateFailure(error, "not_needed"); }
  if (!await steps.confirmSaved()) return "cancelled";
  try {
    await steps.prepare();
    await steps.install();
    return "installed";
  } catch (error) {
    // Prepare may stop the child before a later readiness check fails. Always
    // release the native update gate before any managed backend restoration.
    try { await steps.cancel(); }
    catch (cancelError) { throw new DesktopUpdateFailure(error, "cancel_failed", cancelError); }
    if (!steps.restoreManagedBackend) throw new DesktopUpdateFailure(error, "external_untouched");
    try { await steps.restoreManagedBackend(); }
    catch (restoreError) { throw new DesktopUpdateFailure(error, "restore_failed", restoreError); }
    throw new DesktopUpdateFailure(error, "restored");
  }
}
