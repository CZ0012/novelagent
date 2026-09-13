import { describe, expect, it } from "vitest";
import { DesktopUpdateFailure, runSafeDesktopUpdate } from "./safeDesktopUpdate";

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
    await expect(runSafeDesktopUpdate(failed.steps)).rejects.toMatchObject({ recovery: "not_needed" });
    expect(failed.events).toEqual(["download"]);
    const cancelled = scenario(undefined, true, false);
    expect(await runSafeDesktopUpdate(cancelled.steps)).toBe("cancelled");
    expect(cancelled.events).toEqual(["download", "guard"]);
  });
  it("never installs after failed preparation and unlocks before restoring its managed backend", async () => {
    const test = scenario("prepare");
    await expect(runSafeDesktopUpdate(test.steps)).rejects.toMatchObject({ recovery: "restored" });
    expect(test.events).toEqual(["download", "guard", "prepare", "cancel", "restore"]);
  });
  it("does not start an unrelated external backend on installation failure", async () => {
    const test = scenario("install", false);
    await expect(runSafeDesktopUpdate(test.steps)).rejects.toMatchObject({ recovery: "external_untouched" });
    expect(test.events).toEqual(["download", "guard", "prepare", "install", "cancel"]);
  });
  it("does not restore while a failed cancellation may leave the update gate locked", async () => {
    const test = scenario("prepare");
    test.steps.cancel = async () => { test.events.push("cancel"); throw new Error("locked"); };
    await expect(runSafeDesktopUpdate(test.steps)).rejects.toBeInstanceOf(DesktopUpdateFailure);
    expect(test.events).toEqual(["download", "guard", "prepare", "cancel"]);
  });
});
