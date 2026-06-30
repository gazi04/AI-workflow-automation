<script lang="ts">
	import { Input } from '$lib/components/ui/input';
	import cronstrue from 'cronstrue';

	let { value = $bindable() }: { value: string } = $props();

	const PRESETS: { label: string; cron: string }[] = [
		{ label: 'Every 5 minutes', cron: '*/5 * * * *' },
		{ label: 'Hourly', cron: '0 * * * *' },
		{ label: 'Daily at 09:00', cron: '0 9 * * *' },
		{ label: 'Weekdays at 09:00', cron: '0 9 * * 1-5' },
		{ label: 'Weekly (Mon 09:00)', cron: '0 9 * * 1' },
		{ label: 'Monthly (1st, 09:00)', cron: '0 9 1 * *' }
	];
	const DEFAULT_CRON = '0 9 * * *';
	const CUSTOM = '__custom__';

	const matchesPreset = (v: string) => PRESETS.some((p) => p.cron === v);

	// A schedule node drops with config = {}, so default to a valid cron up front —
	// a saved node must always carry a deployable expression.
	$effect(() => {
		if (!value) value = DEFAULT_CRON;
	});

	// Preset dropdown holds either a preset cron string or the CUSTOM sentinel.
	let mode = $state(value && !matchesPreset(value) ? CUSTOM : value || DEFAULT_CRON);

	function onPresetChange(event: Event) {
		const selected = (event.target as HTMLSelectElement).value;
		mode = selected;
		if (selected !== CUSTOM) value = selected;
	}

	// One standard cron token: *, */n, or a (comma-separated) range list with optional step.
	const CRON_TOKEN = /^(\*|\*\/\d+|\d+(-\d+)?(\/\d+)?(,\d+(-\d+)?(\/\d+)?)*)$/;

	let isValid = $derived.by(() => {
		if (!value) return false;
		const parts = value.trim().split(/\s+/);
		return parts.length === 5 && parts.every((part) => CRON_TOKEN.test(part));
	});

	let humanReadable = $derived.by(() => {
		if (!isValid) return '';
		try {
			return cronstrue.toString(value, { throwExceptionOnParseError: true });
		} catch {
			return '';
		}
	});
</script>

<div class="space-y-2">
	<select
		class="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm"
		value={mode}
		onchange={onPresetChange}
	>
		{#each PRESETS as preset}
			<option value={preset.cron}>{preset.label}</option>
		{/each}
		<option value={CUSTOM}>Custom…</option>
	</select>

	{#if mode === CUSTOM}
		<Input bind:value placeholder="* * * * * (min hour day month weekday)" />
	{/if}

	{#if value}
		{#if isValid}
			<p class="text-[10px] text-muted-foreground">{humanReadable || 'Valid cron expression.'}</p>
		{:else}
			<p class="text-[10px] text-destructive">
				Invalid cron — expected 5 fields: minute hour day month weekday.
			</p>
		{/if}
	{/if}
</div>
