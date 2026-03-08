export type WorkflowRun = {
    id: string;
    name: string;
    state_name: string;
    deployment_id?: string;
    start_time?: string;
    total_run_time?: number;
};

class WorkflowStore {
    latestRuns = $state<WorkflowRun[]>([]);

    setLatestRuns(runs: WorkflowRun[]) {
        this.latestRuns = runs;
    }
}

export const workflowStore = new WorkflowStore();
