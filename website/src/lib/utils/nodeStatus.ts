import type { NodeRunStatus } from '$lib/store/workflowStore.svelte';

/** Tailwind ring classes that light a canvas node by its live run status. */
export function statusRingClass(status: NodeRunStatus | undefined): string {
	switch (status) {
		case 'running':
			return 'ring-4 ring-blue-400 animate-pulse';
		case 'completed':
			return 'ring-4 ring-green-400';
		case 'failed':
			return 'ring-4 ring-red-400';
		default:
			return '';
	}
}
