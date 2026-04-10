<script lang="ts">
	import { Handle, Position } from '@xyflow/svelte';
	import { catalogStore } from '$lib/store/catalogStore.svelte';
	import { ICON_MAP, DEFAULT_ICON } from '$lib/utils/icons';
	import { formatLabel } from '$lib/utils';

	let { data } = $props();

	let definition = $derived(catalogStore.getNodeDef(data.type));
	let Icon = $derived(ICON_MAP[definition?.icon || ''] || DEFAULT_ICON);
</script>

<div
	class="w-64 rounded-xl border-2 border-blue-200 bg-blue-50 px-4 py-3 shadow-lg ring-primary/20 transition-all hover:ring-4"
>
	<div class="mb-2 flex items-center gap-2">
		<div class="rounded bg-blue-500 p-1 text-white">
			<Icon size={14} />
		</div>
		<span class="text-xs font-bold tracking-wider text-blue-700 uppercase">Trigger</span>
	</div>
	<div class="text-sm font-medium text-slate-900">
		{definition?.label || formatLabel(data.type)}
	</div>
	<div class="mt-1 text-[10px] text-slate-500 italic">
		{definition?.description || 'Starts the workflow'}
	</div>

	<Handle type="source" position={Position.Right} class="h-3! w-3! bg-blue-500!" />
</div>
