export interface NonOverlappingPollState {
  inFlight: boolean;
  nextTask: (() => Promise<void>) | null;
}

export function createNonOverlappingPoll(
  task: () => Promise<void>,
  state: NonOverlappingPollState = { inFlight: false, nextTask: null },
): () => Promise<void> {
  return async () => {
    if (state.inFlight) {
      state.nextTask = task;
      return;
    }

    state.inFlight = true;
    try {
      let nextTask: (() => Promise<void>) | null = task;
      while (nextTask !== null) {
        state.nextTask = null;
        await nextTask();
        nextTask = state.nextTask;
      }
    } finally {
      state.inFlight = false;
    }
  };
}
