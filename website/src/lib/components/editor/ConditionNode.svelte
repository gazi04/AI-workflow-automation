<script lang="ts">
	import { Handle, Position, type NodeProps } from '@xyflow/svelte';
	import { catalogStore } from '$lib/store/catalogStore.svelte';
	import { ICON_MAP, DEFAULT_ICON } from '$lib/utils/icons';

	let { data }: NodeProps = $props();

	let definition = $derived(catalogStore.getNodeDef(data.type as string));
	let Icon = $derived(ICON_MAP[definition?.icon || ''] || DEFAULT_ICON);

	// Safely extract rules and match_type using derived state so the node updates instantly
	let rules = $derived(
		Array.isArray((data.config as any)?.rules) ? (data.config as any).rules : []
	);
	let matchType = $derived((data.config as any)?.match_type || 'ALL');

	// Create a dynamic, readable summary to show on the node card
	let conditionSummary = $derived.by(() => {
		if (rules.length === 0) return 'No rules defined.';

		const firstRule = rules[0];
		const varName = firstRule.variable || '[empty]';
		const opName = firstRule.operator ? firstRule.operator.replace('_', ' ') : 'equals';
		const valName = firstRule.value || '[empty]';

		let summary = `${varName} ${opName} ${valName}`;

		if (rules.length > 1) {
			summary += ` ${matchType === 'ALL' ? '(AND' : '(OR'} ${rules.length - 1} more)`;
		}

		return summary;
	});
</script>

<div
	class="min-w-45 rounded-lg border-2 border-orange-500 bg-card p-3 shadow-lg transition-all hover:shadow-xl"
>
	<div class="mb-2 flex items-center gap-2 border-b border-orange-100 pb-2">
		<div class="rounded-md bg-orange-100 p-1.5 text-orange-600">
			<Icon size={16} />
		</div>
		<span class="text-sm font-bold tracking-wider text-muted-foreground uppercase">Condition</span>
	</div>

	<div class="space-y-1">
		<p class="text-xs font-semibold text-foreground">
			{definition?.label || 'Check Condition'}
		</p>
		<p
			class="mt-1 line-clamp-2 rounded bg-muted/50 p-1 font-mono text-[10px] leading-relaxed text-muted-foreground"
		>
			{conditionSummary}
		</p>
	</div>

	<Handle type="target" position={Position.Left} class="h-3! w-3! bg-orange-500!" />

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
