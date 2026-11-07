import { describe, expect, it, vi } from "vitest";

import {
  createNonOverlappingPoll,
  type NonOverlappingPollState,
} from "../lib/create-non-overlapping-poll";

describe("createNonOverlappingPoll", () => {
  it("queues the latest refresh and runs it after an in-flight poll settles", async () => {
    const state: NonOverlappingPollState = { inFlight: false, nextTask: null };
    const events: string[] = [];
    let finishFirst: (() => void) | undefined;
    let finishNext: (() => void) | undefined;
    const firstTask = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          events.push("first-started");
          finishFirst = () => {
            events.push("first-finished");
            resolve();
          };
        }),
    );
    const queuedTask = vi.fn(async () => {
      events.push("queued-task");
    });
    const latestTask = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          events.push("latest-started");
          finishNext = () => {
            events.push("latest-finished");
            resolve();
          };
        }),
    );
    const firstPoll = createNonOverlappingPoll(firstTask, state);
    const replayedPoll = createNonOverlappingPoll(queuedTask, state);
    const latestPoll = createNonOverlappingPoll(latestTask, state);

    const currentPoll = firstPoll();
    await replayedPoll();
    await latestPoll();
    expect(firstTask).toHaveBeenCalledTimes(1);
    expect(queuedTask).not.toHaveBeenCalled();
    expect(latestTask).not.toHaveBeenCalled();

    finishFirst?.();
    await Promise.resolve();
    expect(events).toEqual(["first-started", "first-finished", "latest-started"]);
    expect(latestTask).toHaveBeenCalledTimes(1);

    finishNext?.();
    await currentPoll;
    expect(events).toEqual([
      "first-started",
      "first-finished",
      "latest-started",
      "latest-finished",
    ]);
  });
});
