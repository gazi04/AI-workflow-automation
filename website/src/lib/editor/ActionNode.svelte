<script lang="ts">
	import { Handle, Position } from '@xyflow/svelte';
	import { Settings2, Play } from 'lucide-svelte';
	let { data } = $props();
</script>

<div
	class="w-64 rounded-xl border-2 border-slate-200 bg-white px-4 py-3 shadow-lg ring-primary/20 transition-all hover:ring-4"
>
	<Handle type="target" position={Position.Left} class="!h-3 !w-3 !bg-slate-400" />

	<div class="mb-2 flex items-center justify-between">
		<div class="flex items-center gap-2">
			<div class="rounded bg-slate-800 p-1 text-white">
				<Play size={14} />
			</div>
			<span class="text-[10px] font-bold tracking-wider text-slate-500 uppercase"
				>{data.type.replace('_', ' ')}</span
			>
		</div>
		<Settings2 size={14} class="text-slate-400" />
	</div>

	<div class="text-sm font-medium text-slate-900">
		{data.config.user_prompt || data.type}
	</div>

	<Handle type="source" position={Position.Right} class="!h-3 !w-3 !bg-slate-400" />
</div>
