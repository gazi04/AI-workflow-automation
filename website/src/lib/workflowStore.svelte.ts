import type { components } from '$lib/types/schema';

type WorkflowRun = components['schemas']['WorkflowRun'];

class WorkflowStore {
	latestRuns = $state<WorkflowRun[]>([]);

	setLatestRuns(runs: WorkflowRun[]) {
		this.latestRuns = runs;
	}
}

export const workflowStore = new WorkflowStore();
