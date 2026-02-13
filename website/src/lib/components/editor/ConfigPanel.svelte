<script lang="ts">
	import { ACTION_DEFINITIONS } from '$lib/schemas/workflow';
	import { X } from 'lucide-svelte';
	import { Input } from '$lib/components/ui/input';
	import { Textarea } from '$lib/components/ui/textarea';
	import { Label } from '$lib/components/ui/label';
	import {
		Select,
		SelectContent,
		SelectItem,
		SelectTrigger,
	} from '$lib/components/ui/select';

	let { node = $bindable(), onClose } = $props();

	// 1. Determine which definition to use based on the node type
	let currentType = $derived(node.data.type);
	let definition = $derived(ACTION_DEFINITIONS[currentType] || { fields: [] });

	// 2. Handle Type Switching (The Logic Challenge)
	function handleTypeChange(newType: string) {
		// Update the type
		node.data.type = newType;
		node.data.label = ACTION_DEFINITIONS[newType]?.label || newType;

		// Reset config to avoid "ghost" data (e.g. smart_draft data sticking around in send_email)
		node.data.config = {};

		// Pre-fill empty keys so the UI inputs are reactive
		ACTION_DEFINITIONS[newType].fields.forEach((f) => {
			node.data.config[f.key] = '';
		});
	}
</script>

<aside class="absolute top-0 right-0 z-20 flex h-full w-96 flex-col border-l bg-card shadow-xl">
	<div class="flex items-center justify-between border-b bg-muted/20 p-4">
		<h2 class="text-sm font-bold tracking-wide uppercase">Configuration</h2>
		<button onclick={onClose} class="rounded p-1 hover:bg-slate-200">
			<X size={16} />
		</button>
	</div>

	<div class="flex-1 space-y-6 overflow-y-auto p-6">
		<div class="space-y-2">
			<Label>Action Type</Label>
			<select
				class="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm"
				value={currentType}
				onchange={(e) => handleTypeChange(e.currentTarget.value)}
			>
				{#each Object.entries(ACTION_DEFINITIONS) as [key, def]}
					<option value={key}>{def.label}</option>
				{/each}
			</select>
		</div>

		<hr />

		{#each definition.fields as field}
			<div class="space-y-2">
				<Label>{field.label}</Label>

				{#if field.type === 'textarea'}
					<Textarea
						bind:value={node.data.config[field.key]}
						placeholder={`Enter ${field.label}...`}
						rows={5}
					/>
				{:else}
					<Input
						type="text"
						bind:value={node.data.config[field.key]}
						placeholder={`Enter ${field.label}...`}
					/>
				{/if}

				<p class="text-[10px] text-muted-foreground">
					Mapped to: <code class="rounded bg-slate-100 px-1">{field.key}</code>
				</p>
			</div>
		{/each}

		{#if definition.fields.length === 0}
			<div class="rounded bg-yellow-50 p-3 text-sm text-yellow-600">
				⚠️ No configuration fields defined for this type.
			</div>
		{/if}
	</div>
</aside>
