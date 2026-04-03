<script lang="ts">
	import { Handle, Position, type NodeProps } from '@xyflow/svelte';
	import { GitBranch } from 'lucide-svelte';

	let { data }: NodeProps = $props();
</script>

<div
	class="min-w-45 rounded-lg border-2 border-orange-500 bg-card p-3 shadow-lg transition-all hover:shadow-xl"
>
	<div class="mb-2 flex items-center gap-2 border-b border-orange-100 pb-2">
		<div class="rounded-md bg-orange-100 p-1.5 text-orange-600">
			<GitBranch size={16} />
		</div>
		<span class="text-sm font-bold tracking-wider text-muted-foreground uppercase">Condition</span>
	</div>

	<div class="space-y-1">
		<p class="text-xs font-semibold text-foreground">
			{data.type === 'condition' ? 'Check Condition' : data.type}
		</p>
		<p class="line-clamp-2 text-[10px] leading-relaxed text-muted-foreground">
			{(data.config as any)?.expression || 'Branching logic based on rules.'}
		</p>
	</div>

	<!-- Input Handle -->
	<Handle type="target" position={Position.Left} class="h-3! w-3! bg-orange-500!" />

	<!-- True Output Handle (Top Right) -->
	<div class="absolute top-1/4 -right-3 flex items-center gap-1">
		<span class="text-[8px] font-bold text-green-600">TRUE</span>
		<Handle
			id="true_path"
			type="source"
			position={Position.Right}
			class="h-3! w-3! bg-green-500!"
			style="top: 0;"
		/>
	</div>

	<!-- False Output Handle (Bottom Right) -->
	<div class="absolute -right-3 bottom-1/4 flex items-center gap-1">
		<span class="text-[8px] font-bold text-red-600">FALSE</span>
		<Handle
			id="false_path"
			type="source"
			position={Position.Right}
			class="h-3! w-3! bg-red-500!"
			style="top: 0;"
		/>
	</div>
</div>
