import { describe, expect, it } from "vitest";
import { DesktopUpdateFailure, isWindowsUpdateFileLock, runSafeDesktopUpdate } from "./safeDesktopUpdate";

function scenario(failAt?: string, managed = true, confirmed = true) {
  const events: string[] = [];
  const step = (name: string) => async () => { events.push(name); if (failAt === name) throw new Error(name); };
  return { events, steps: { download: step("download"), confirmSaved: async () => { events.push("guard"); return confirmed; }, prepare: step("prepare"), install: step("install"), cancel: step("cancel"), restoreManagedBackend: managed ? step("restore") : null } };
}

describe("safe desktop update sequence", () => {
  it("downloads before the author guard and prepares only immediately before installation", async () => {
    const test = scenario();
    expect(await runSafeDesktopUpdate(test.steps)).toBe("installed");
    expect(test.events).toEqual(["download", "guard", "prepare", "install"]);
  });
  it("does not stop a backend when download fails or author cancels unsaved edits", async () => {
    const failed = scenario("download");
    await expect(runSafeDesktopUpdate(failed.steps)).rejects.toMatchObject({ stage: "download", cause: new Error("download"), recovery: "not_needed", canRetry: true });
    expect(failed.events).toEqual(["download"]);
    const cancelled = scenario(undefined, true, false);
    expect(await runSafeDesktopUpdate(cancelled.steps)).toBe("cancelled");
    expect(cancelled.events).toEqual(["download", "guard"]);
  });
  it("never installs after failed preparation and unlocks before restoring its managed backend", async () => {
    const test = scenario("prepare");
    await expect(runSafeDesktopUpdate(test.steps)).rejects.toMatchObject({ stage: "preparation", cause: new Error("prepare"), recovery: "restored", canRetry: true });
    expect(test.events).toEqual(["download", "guard", "prepare", "cancel", "restore"]);
  });
  it("does not start an unrelated external backend on installation failure", async () => {
    const test = scenario("install", false);
    await expect(runSafeDesktopUpdate(test.steps)).rejects.toMatchObject({ stage: "installation", cause: new Error("install"), recovery: "external_untouched", canRetry: true });
    expect(test.events).toEqual(["download", "guard", "prepare", "install", "cancel"]);
  });
  it("preserves the original installation error after restoring its managed backend", async () => {
    const test = scenario();
    const original = new Error("Installer could not start");
    test.steps.install = async () => { test.events.push("install"); throw original; };
    const failure = await runSafeDesktopUpdate(test.steps).catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(DesktopUpdateFailure);
    expect((failure as DesktopUpdateFailure).cause).toBe(original);
    expect(failure).toMatchObject({ stage: "installation", recovery: "restored", canRetry: true });
    expect(test.events).toEqual(["download", "guard", "prepare", "install", "cancel", "restore"]);
  });
  it("keeps the original stage and both errors when managed recovery fails, without offering immediate retry", async () => {
    const test = scenario();
    const original = "The backend is in use (os error 32)";
    const recoveryError = new Error("Backend did not become ready");
    test.steps.prepare = async () => { test.events.push("prepare"); throw original; };
    test.steps.restoreManagedBackend = async () => { test.events.push("restore"); throw recoveryError; };
    const failure = await runSafeDesktopUpdate(test.steps).catch((error: unknown) => error);
    expect(failure).toMatchObject({ stage: "preparation", cause: original, recovery: "restore_failed", canRetry: false });
    expect((failure as DesktopUpdateFailure).recoveryError).toBe(recoveryError);
    expect(test.events).toEqual(["download", "guard", "prepare", "cancel", "restore"]);
  });
  it("does not restore while a failed cancellation may leave the update gate locked", async () => {
    const test = scenario("prepare");
    const recoveryError = new Error("locked");
    test.steps.cancel = async () => { test.events.push("cancel"); throw recoveryError; };
    await expect(runSafeDesktopUpdate(test.steps)).rejects.toMatchObject({ stage: "preparation", cause: new Error("prepare"), recovery: "cancel_failed", recoveryError, canRetry: false });
    expect(test.events).toEqual(["download", "guard", "prepare", "cancel"]);
  });
  it("offers file-lock guidance only for original Windows sharing or lock errors", () => {
    expect(isWindowsUpdateFileLock("后端文件无法替换 (os error 32)")).toBe(true);
    expect(isWindowsUpdateFileLock(new Error("File lock (os error 33)"))).toBe(true);
    for (const cause of ["Access denied (os error 5)", "Failure (os error 320)", "Backend did not start", "Another workspace action is still running", { message: "os error 32" }, null]) {
      expect(isWindowsUpdateFileLock(cause)).toBe(false);
    }
  });
});
