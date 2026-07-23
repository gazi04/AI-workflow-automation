import type { components } from '$lib/types/schema';

type WorkflowRun = components['schemas']['WorkflowRun'];

export type NodeRunStatus = 'running' | 'completed' | 'failed';

/** Key node run state by `${workflowId}:${nodeId}` so ids can't collide across workflows. */
function nodeKey(workflowId: string, nodeId: string) {
	return `${workflowId}:${nodeId}`;
}

class WorkflowStore {
	latestRuns = $state<WorkflowRun[]>([]);
	// Live per-node execution status for the editor canvas, keyed by workflow+node.
	nodeRunStatus = $state<Record<string, NodeRunStatus>>({});

	setLatestRuns(runs: WorkflowRun[]) {
		this.latestRuns = runs;
	}

	setNodeStatus(workflowId: string, nodeId: string, status: NodeRunStatus) {
		this.nodeRunStatus = {
			...this.nodeRunStatus,
			[nodeKey(workflowId, nodeId)]: status
		};
	}

	getNodeStatus(workflowId: string, nodeId: string): NodeRunStatus | undefined {
		return this.nodeRunStatus[nodeKey(workflowId, nodeId)];
	}

	/** Drop all node statuses for one workflow (called shortly after a run finishes). */
	clearRun(workflowId: string) {
		const prefix = `${workflowId}:`;
		const next: Record<string, NodeRunStatus> = {};
		for (const [key, value] of Object.entries(this.nodeRunStatus)) {
			if (!key.startsWith(prefix)) next[key] = value;
		}
		this.nodeRunStatus = next;
	}
}

export const workflowStore = new WorkflowStore();
