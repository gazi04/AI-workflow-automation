<script lang="ts">
	import { catalogStore } from '$lib/store/catalogStore.svelte';
	import { formatLabel } from '$lib/utils';
	import { X, Trash2 } from 'lucide-svelte';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { Textarea } from '$lib/components/ui/textarea';

	let { node = $bindable(), nodes = [], onClose } = $props();

	let availableVariables = $derived.by(() => {
		const vars: { label: string; value: string }[] = [];
		nodes.forEach((n) => {
			if (n.id === node.id) return;

			// Use the specific backend type for definition lookup
			const nodeType = n.data.type;
			const def = catalogStore.getNodeDef(nodeType);

			if (def && def.outputs) {
				// Use the actual node ID as the prefix for all nodes (including triggers)
				const prefix = n.id;
				def.outputs.forEach((out) => {
					vars.push({
						label: `${n.data.label || formatLabel(nodeType)} → ${out}`,
						value: `{{${prefix}.${out}}}`
					});
				});
			}
		});
		return vars;
	});

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

		if (node.data.type === 'if_condition' && config) {
			if (!Array.isArray(config.rules)) {
				console.log('Healing workflow config: initializing rules array for if_condition');
				config.rules = [];
			}
			if (!config.match_type) {
				config.match_type = 'ALL';
			}
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

		if (newType === 'if_condition') {
			newConfig.rules = [];
			newConfig.match_type = 'ALL';
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

		{#if definition && node.data.type !== 'if_condition'}
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

		{#if node.data.type === 'if_condition'}
			<div class="space-y-4">
				<div class="space-y-2">
					<Label>Matching Strategy</Label>
					<select
						class="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm"
						bind:value={node.data.config.match_type}
					>
						<option value="ALL">All rules match (AND)</option>
						<option value="ANY">Any rule matches (OR)</option>
					</select>
				</div>

				<div class="space-y-3">
					<div class="flex items-center justify-between">
						<Label>Rules</Label>
						<button
							onclick={() =>
								node.data.config.rules.push({
									variable: '',
									operator: 'equals',
									value: ''
								})}
							class="text-[10px] font-bold text-primary hover:underline"
						>
							+ Add Rule
						</button>
					</div>

					{#each node.data.config.rules as rule, i}
						<div class="space-y-2 rounded-md border bg-muted/30 p-3">
							<div class="flex items-center justify-between">
								<span class="text-[10px] font-bold tracking-tight text-muted-foreground uppercase"
									>Rule {i + 1}</span
								>
								<button
									onclick={() => node.data.config.rules.splice(i, 1)}
									class="text-muted-foreground hover:text-destructive"
								>
									<Trash2 size={12} />
								</button>
							</div>
							<div class="space-y-1">
								<Label class="text-[10px]">Variable</Label>
								<select
									class="flex h-8 w-full items-center justify-between rounded-md border border-input bg-background px-2 py-1 text-xs"
									bind:value={rule.variable}
								>
									<option value="" disabled selected>Select variable...</option>
									{#each availableVariables as v}
										<option value={v.value}>{v.label}</option>
									{/each}
								</select>
							</div>
							<div class="grid grid-cols-2 gap-2">
								<div class="space-y-1">
									<Label class="text-[10px]">Operator</Label>
									<select
										class="flex h-8 w-full items-center justify-between rounded-md border border-input bg-background px-2 py-1 text-xs"
										bind:value={rule.operator}
									>
										<option value="equals">Equals</option>
										<option value="contains">Contains</option>
										<option value="exists">Exists</option>
										<option value="greater_than">Greater than</option>
										<option value="less_than">Less than</option>
									</select>
								</div>
								<div class="space-y-1">
									<Label class="text-[10px]">Value</Label>
									<Input bind:value={rule.value} placeholder="Value..." class="h-8 text-xs" />
								</div>
							</div>
						</div>
					{/each}

					{#if node.data.config.rules.length === 0}
						<p class="py-4 text-center text-xs text-muted-foreground italic">
							No rules defined. This condition will always match by default.
						</p>
					{/if}
				</div>
			</div>
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
