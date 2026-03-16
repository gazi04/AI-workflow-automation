<script lang="ts">
	import { onMount } from 'svelte';
	import { catalogStore } from '$lib/catalogStore.svelte';
	import type { components } from '$lib/types/schema';

	type NodeDefinition = components['schemas']['NodeDefinition'];

	const ICON_MAP: Record<string, string> = {
		'lucide-mail': `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>`,
		'lucide-hand': `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 11V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2"/><path d="M14 10V4a2 2 0 0 0-2-2a2 2 0 0 0-2 2v2"/><path d="M10 10.5V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/></svg>`,
		'lucide-calendar': `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/></svg>`,
		'lucide-file-spreadsheet': `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M8 13h2"/><path d="M14 13h2"/><path d="M8 17h2"/><path d="M14 17h2"/></svg>`,
		'lucide-send': `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>`,
		'lucide-reply': `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 17 4 12 9 7"/><path d="M20 18v-2a4 4 0 0 0-4-4H4"/></svg>`,
		'lucide-tag': `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r=".5" fill="currentColor"/></svg>`,
		'lucide-sparkles': `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/></svg>`,
		'lucide-file-text': `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>`,
		'lucide-slack': `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="3" height="8" x="13" y="2" rx="1.5"/><path d="M19 8.5V10h1.5A1.5 1.5 0 1 0 19 8.5"/><rect width="3" height="8" x="8" y="14" rx="1.5"/><path d="M5 15.5V14H3.5A1.5 1.5 0 1 0 5 15.5"/><rect width="8" height="3" x="14" y="13" rx="1.5"/><path d="M15.5 19H14v1.5a1.5 1.5 0 1 0 1.5-1.5"/><rect width="8" height="3" x="2" y="8" rx="1.5"/><path d="M8.5 5H10V3.5A1.5 1.5 0 1 0 8.5 5"/></svg>`
	};

	const DEFAULT_ICON = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/></svg>`;

	let { onDragStart }: { onDragStart?: (node: NodeDefinition, nodeType: 'trigger' | 'action') => void } = $props();

	const grouped = $derived.by(() => {
		if (!catalogStore.catalog) return { triggers: {}, actions: {} };

		const group = (nodes: NodeDefinition[]) =>
			nodes.reduce<Record<string, NodeDefinition[]>>((acc, node) => {
				(acc[node.category] ??= []).push(node);
				return acc;
			}, {});

		return {
			triggers: group(catalogStore.catalog.triggers),
			actions: group(catalogStore.catalog.actions)
		};
	});

	function handleDragStart(event: DragEvent, node: NodeDefinition, nodeType: 'trigger' | 'action') {
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
		<h2 class="text-xs font-bold uppercase tracking-widest text-muted-foreground">Node Catalog</h2>
	</div>

	<div class="flex-1 overflow-y-auto p-3">
		{#if catalogStore.isLoading}
			<!-- Loading skeleton -->
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
			<!-- Triggers -->
			<div class="mb-4">
				<p class="mb-2 px-1 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
					Triggers
				</p>
				{#each Object.entries(grouped.triggers) as [category, nodes]}
					<div class="mb-3">
						<p class="mb-1 px-1 text-[10px] text-muted-foreground/70">{category}</p>
						{#each nodes as node}
							<div
								role="button"
								tabindex="0"
								draggable="true"
								ondragstart={(e) => handleDragStart(e, node, 'trigger')}
								class="mb-1 flex cursor-grab items-center gap-2 rounded-md border border-transparent px-2 py-2 text-sm transition-colors hover:border-border hover:bg-accent active:cursor-grabbing"
							>
								<span class="text-primary opacity-80">{@html ICON_MAP[node.type] ?? DEFAULT_ICON}</span>
								<span class="font-medium">{node.label}</span>
							</div>
						{/each}
					</div>
				{/each}
			</div>

			<hr class="mb-4" />

			<!-- Actions -->
			<div>
				<p class="mb-2 px-1 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
					Actions
				</p>
				{#each Object.entries(grouped.actions) as [category, nodes]}
					<div class="mb-3">
						<p class="mb-1 px-1 text-[10px] text-muted-foreground/70">{category}</p>
						{#each nodes as node}
							<div
								role="button"
								tabindex="0"
								draggable="true"
								ondragstart={(e) => handleDragStart(e, node, 'action')}
								class="mb-1 flex cursor-grab items-center gap-2 rounded-md border border-transparent px-2 py-2 text-sm transition-colors hover:border-border hover:bg-accent active:cursor-grabbing"
							>
								<span class="text-primary opacity-80">{@html ICON_MAP[node.type] ?? DEFAULT_ICON}</span>
								<span class="font-medium">{node.label}</span>
							</div>
						{/each}
					</div>
				{/each}
			</div>
		{/if}
	</div>
</aside>
