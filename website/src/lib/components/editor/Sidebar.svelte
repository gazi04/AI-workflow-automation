<script lang="ts">
	import { onMount } from 'svelte';
	import { catalogStore } from '$lib/store/catalogStore.svelte';
	import type { components } from '$lib/types/schema';
	import { ICON_MAP, DEFAULT_ICON } from '$lib/utils/icons';

	type NodeDefinition = components['schemas']['NodeDefinition'];

	let {
		onDragStart
	}: { onDragStart?: (node: NodeDefinition, nodeType: 'trigger' | 'action' | 'condition') => void } = $props();

	const grouped = $derived.by(() => {
		if (!catalogStore.catalog) return { triggers: {}, actions: {}, conditions: {} };

		const group = (nodes: NodeDefinition[]) =>
			nodes.reduce<Record<string, NodeDefinition[]>>((acc, node) => {
				(acc[node.category] ??= []).push(node);
				return acc;
			}, {});

		return {
			triggers: group(catalogStore.catalog.triggers),
			actions: group(catalogStore.catalog.actions),
			conditions: group(catalogStore.catalog.conditions ?? [])
		};
	});

	function handleDragStart(
		event: DragEvent,
		node: NodeDefinition,
		nodeType: 'trigger' | 'action' | 'condition'
	) {
		if (!event.dataTransfer) return;
		event.dataTransfer.effectAllowed = 'move';
		event.dataTransfer.setData('application/reactflow-type', nodeType);
		event.dataTransfer.setData('application/reactflow-nodetype', node.type);
		onDragStart?.(node, nodeType);
	}

	onMount(() => catalogStore.load());
</script>

<aside class="flex h-full w-64 shrink-0 flex-col border-r bg-card">
	<div class="border-b px-4 py-3">
		<h2 class="text-xs font-bold tracking-widest text-muted-foreground uppercase">Node Catalog</h2>
	</div>

	<div class="flex-1 overflow-y-auto p-3">
		{#if catalogStore.isLoading}
			<div class="space-y-2">
				{#each Array(5) as _}
					<div class="h-10 animate-pulse rounded-md bg-muted"></div>
				{/each}
			</div>
		{:else if catalogStore.error}
			<div class="rounded-md bg-destructive/10 p-3 text-xs text-destructive">
				Failed to load catalog: {catalogStore.error}
			</div>
		{:else}
			{#snippet nodeItem(node: NodeDefinition, type: 'trigger' | 'action' | 'condition')}
				{@const Icon = ICON_MAP[node.icon] ?? DEFAULT_ICON}
				<div
					role="button"
					tabindex="0"
					draggable="true"
					ondragstart={(e) => handleDragStart(e, node, type)}
					class="mb-1 flex cursor-grab items-center gap-2 rounded-md border border-transparent px-2 py-2 text-sm transition-colors hover:border-border hover:bg-accent active:cursor-grabbing"
				>
					<span class="text-primary opacity-80">
						<Icon size={16} strokeWidth={2} />
					</span>
					<span class="font-medium">{node.label}</span>
				</div>
			{/snippet}

			<div class="mb-4">
				<p class="mb-2 px-1 text-[10px] font-bold tracking-widest text-muted-foreground uppercase">
					Triggers
				</p>
				{#each Object.entries(grouped.triggers) as [category, nodes]}
					<div class="mb-3">
						<p class="mb-1 px-1 text-[10px] text-muted-foreground/70">{category}</p>
						{#each nodes as node}
							{@render nodeItem(node, 'trigger')}
						{/each}
					</div>
				{/each}
			</div>

			<div class="mb-4">
				<p class="mb-2 px-1 text-[10px] font-bold tracking-widest text-muted-foreground uppercase">
					Conditions
				</p>
				{#each Object.entries(grouped.conditions) as [category, nodes]}
					<div class="mb-3">
						<p class="mb-1 px-1 text-[10px] text-muted-foreground/70">{category}</p>
						{#each nodes as node}
							{@render nodeItem(node, 'condition')}
						{/each}
					</div>
				{/each}
			</div>

			<hr class="mb-4" />

			<div>
				<p class="mb-2 px-1 text-[10px] font-bold tracking-widest text-muted-foreground uppercase">
					Actions
				</p>
				{#each Object.entries(grouped.actions) as [category, nodes]}
					<div class="mb-3">
						<p class="mb-1 px-1 text-[10px] text-muted-foreground/70">{category}</p>
						{#each nodes as node}
							{@render nodeItem(node, 'action')}
						{/each}
					</div>
				{/each}
			</div>
		{/if}
	</div>
</aside>
