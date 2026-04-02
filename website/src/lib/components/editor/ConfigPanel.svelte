<script lang="ts">
	import { catalogStore } from '$lib/store/catalogStore.svelte';
	import { X } from 'lucide-svelte';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { Textarea } from '$lib/components/ui/textarea';

	let { node = $bindable(), onClose } = $props();

	let nodeCategory = $derived(node.type as 'trigger' | 'action' | 'condition');
	let availableDefinitions = $derived.by(() => {
		if (!catalogStore.catalog) return [];
		if (nodeCategory === 'trigger') return catalogStore.catalog.triggers;
		if (nodeCategory === 'action') return catalogStore.catalog.actions;
		if (nodeCategory === 'condition') return catalogStore.catalog.conditions;
		return [];
	});

	let definition = $derived(catalogStore.getNodeDef(node.data.type));

	$effect(() => {
		const config = node.data.config;
		if (node.data.type === 'email_received' && config) {
			if (config.from_email && !config.from) {
				console.log('Healing workflow config: moving from_email to from');
				config.from = config.from_email;
				delete config.from_email;
			}
		}

		if (node.data.type === 'label_email' && config && !config.label_info) {
			console.log('Healing workflow config: initializing label_info');
			config.label_info = {
				name: '',
				color: { backgroundColor: '#ffffff', textColor: '#000000' }
			};
		}
	});

	function handleTypeChange(newType: string) {
		const def = catalogStore.getNodeDef(newType);
		if (!def) return;

		node.data.type = newType;
		node.data.label = def.label;

		const newConfig: Record<string, any> = {};
		def.fields.forEach((f) => {
			newConfig[f.key] = '';
		});

		if (newType === 'label_email') {
			newConfig.label_info = {
				name: '',
				color: { backgroundColor: '#ffffff', textColor: '#000000' }
			};
		}

		node.data.config = newConfig;
	}
</script>

<aside class="absolute top-0 right-0 z-20 flex h-full w-96 flex-col border-l bg-card shadow-xl">
	<div class="flex items-center justify-between border-b bg-muted/20 p-4">
		<h2 class="text-sm font-bold tracking-wide uppercase">
			Configure {nodeCategory}
		</h2>
		<button onclick={onClose} class="rounded p-1 hover:bg-slate-200">
			<X size={16} />
		</button>
	</div>

	<div class="flex-1 space-y-6 overflow-y-auto p-6">
		<div class="space-y-2">
			<Label>{nodeCategory === 'trigger' ? 'Trigger Event' : 'Action Type'}</Label>
			<select
				class="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm"
				value={node.data.type}
				onchange={(e) => handleTypeChange(e.currentTarget.value)}
			>
				{#each availableDefinitions as def}
					<option value={def.type}>{def.label}</option>
				{/each}
			</select>
		</div>

		<hr />

		{#if definition}
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
		{/if}

		{#if node.data.type === 'label_email' && node.data.config.label_info}
			<div class="space-y-4">
				<div class="space-y-2">
					<Label>Label Name</Label>
					<Input type="text" bind:value={node.data.config.label_info.name} />
				</div>
				<div class="grid grid-cols-2 gap-4">
					<div class="space-y-2">
						<Label>Background Color</Label>
						<Input
							type="color"
							bind:value={node.data.config.label_info.color.backgroundColor}
							class="h-10 w-full p-1"
						/>
					</div>
					<div class="space-y-2">
						<Label>Text Color</Label>
						<Input
							type="color"
							bind:value={node.data.config.label_info.color.textColor}
							class="h-10 w-full p-1"
						/>
					</div>
				</div>
			</div>
		{/if}

		{#if definition && definition.fields.length === 0 && node.data.type !== 'label_email'}
			<div class="rounded bg-yellow-50 p-3 text-sm text-yellow-600">
				⚠️ No configuration fields defined for this type.
			</div>
		{:else if !definition}
			<div class="rounded bg-red-50 p-3 text-sm text-red-600">
				⚠️ Unrecognized node type: <code class="font-bold">{node.data.type}</code>. Please select a
				valid type from the list above.
			</div>
		{/if}
	</div>
</aside>
