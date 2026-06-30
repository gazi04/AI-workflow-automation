<script lang="ts">
	import { catalogStore } from '$lib/store/catalogStore.svelte';
	import { formatLabel } from '$lib/utils';
	import { X, Trash2, Copy, Check } from 'lucide-svelte';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { Textarea } from '$lib/components/ui/textarea';
	import CronField from './CronField.svelte';
	import { BASE_URL } from '$lib/api/client';

	let {
		node = $bindable(),
		nodes = [],
		workflowId = null,
		webhookSecret = null,
		onClose,
		onDelete
	}: {
		node: any;
		nodes?: any[];
		workflowId?: string | null;
		webhookSecret?: string | null;
		onClose: () => void;
		onDelete: () => void;
	} = $props();

	let webhookUrl = $derived(
		workflowId && workflowId !== 'new' ? `${BASE_URL}/api/webhooks/trigger/${workflowId}` : ''
	);
	let copied = $state('');
	async function copy(text: string, which: string) {
		try {
			await navigator.clipboard.writeText(text);
			copied = which;
			setTimeout(() => (copied = ''), 1500);
		} catch {
			/* clipboard unavailable */
		}
	}

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

		if (node.data.type === 'label_email' && config) {
			// Migrate old label_info format to new flat fields
			if (config.label_info) {
				console.log('Migrating label_info to flattened fields');
				config.label_name = config.label_info.name || '';
				if (config.label_info.color) {
					config.background_color = config.label_info.color.backgroundColor || '#999999';
					config.text_color = config.label_info.color.textColor || '#f3f3f3';
				}
				delete config.label_info;
			}

			// Ensure defaults for new format
			if (config.label_name === undefined) config.label_name = '';
			if (!config.background_color) config.background_color = '#999999';
			if (!config.text_color) config.text_color = '#f3f3f3';
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
			newConfig.label_name = '';
			newConfig.background_color = '#999999';
			newConfig.text_color = '#f3f3f3';
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
		<div class="flex items-center gap-1">
			<button
				onclick={onDelete}
				class="rounded p-1 text-destructive hover:bg-slate-200"
				title="Delete node"
			>
				<Trash2 size={16} />
			</button>
			<button onclick={onClose} class="rounded p-1 hover:bg-slate-200">
				<X size={16} />
			</button>
		</div>
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
					{:else if field.type === 'select'}
						<select
							class="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm"
							bind:value={node.data.config[field.key]}
						>
							{#each field.options || [] as option}
								<option value={option}>{option}</option>
							{/each}
						</select>
					{:else if field.type === 'cron'}
						<CronField bind:value={node.data.config[field.key]} />
					{:else if field.type === 'rule_builder'}
						<div class="space-y-3">
							<div class="flex items-center justify-between">
								<button
									onclick={() => {
										if (!node.data.config[field.key]) node.data.config[field.key] = [];
										node.data.config[field.key].push({
											variable: '',
											operator: 'equals',
											value: ''
										});
									}}
									class="text-[10px] font-bold text-primary hover:underline"
								>
									+ Add Rule
								</button>
							</div>

							{#each node.data.config[field.key] || [] as rule, i}
								<div class="space-y-2 rounded-md border bg-muted/30 p-3">
									<div class="flex items-center justify-between">
										<span
											class="text-[10px] font-bold tracking-tight text-muted-foreground uppercase"
											>Rule {i + 1}</span
										>
										<button
											onclick={() => node.data.config[field.key].splice(i, 1)}
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

							{#if (node.data.config[field.key] || []).length === 0}
								<p class="py-4 text-center text-xs text-muted-foreground italic">
									No rules defined. This condition will always match by default.
								</p>
							{/if}
						</div>
					{:else}
						<Input
							type={field.type}
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

		{#if node.data.type === 'webhook'}
			<div class="space-y-2 rounded-md border bg-muted/30 p-3">
				<Label class="text-xs font-bold tracking-tight uppercase">Webhook URL</Label>
				{#if webhookUrl && webhookSecret}
					<p class="text-[10px] text-muted-foreground">
						Send a <code class="rounded bg-slate-100 px-1">POST</code> here to run this workflow.
					</p>
					<div class="flex items-center gap-1">
						<Input value={webhookUrl} readonly class="h-8 text-xs" />
						<button
							onclick={() => copy(webhookUrl, 'url')}
							class="rounded p-1.5 hover:bg-slate-200"
							title="Copy URL"
						>
							{#if copied === 'url'}<Check size={14} />{:else}<Copy size={14} />{/if}
						</button>
					</div>
					<Label class="text-[10px]">Header <code>X-Webhook-Secret</code></Label>
					<div class="flex items-center gap-1">
						<Input value={webhookSecret} readonly type="password" class="h-8 text-xs" />
						<button
							onclick={() => copy(webhookSecret, 'secret')}
							class="rounded p-1.5 hover:bg-slate-200"
							title="Copy secret"
						>
							{#if copied === 'secret'}<Check size={14} />{:else}<Copy size={14} />{/if}
						</button>
					</div>
					<p class="text-[10px] text-muted-foreground">
						Keep this secret private — anyone with it can trigger the workflow. The posted JSON is
						available downstream as
						<code class="rounded bg-slate-100 px-1">{`{{${node.id}.body}}`}</code>.
					</p>
				{:else}
					<p class="text-[10px] text-muted-foreground">
						Save the workflow to generate its webhook URL and secret.
					</p>
				{/if}
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
