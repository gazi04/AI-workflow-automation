<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { Switch } from '$lib/components/ui/switch';
	import { Loader } from 'lucide-svelte';
	import { toast, Toaster } from 'svelte-sonner';

	type Settings = {
		timezone: string;
		default_llm_provider: string;
		notification_preferences: Record<string, boolean>;
	};

	const PROVIDERS = ['deepseek', 'openai', 'anthropic', 'azure'];

	let settings = $state<Settings | null>(null);
	let isLoading = $state(true);
	let isSaving = $state(false);

	async function loadSettings() {
		try {
			settings = await api.get<Settings>('/api/user/settings');
		} catch (err) {
			console.error('Failed to load settings', err);
			toast.error('Failed to load settings.');
		} finally {
			isLoading = false;
		}
	}

	async function saveSettings() {
		if (!settings) return;
		isSaving = true;
		try {
			settings = await api.patch<Settings>('/api/user/settings', {
				timezone: settings.timezone,
				default_llm_provider: settings.default_llm_provider,
				notification_preferences: settings.notification_preferences
			});
			toast.success('Settings saved.');
		} catch (err) {
			console.error('Failed to save settings', err);
			toast.error('Failed to save settings.');
		} finally {
			isSaving = false;
		}
	}

	onMount(loadSettings);
</script>

<Toaster richColors position="top-right" />

<div class="mx-auto max-w-2xl p-6 lg:p-10">
	<header class="mb-8">
		<h1 class="text-3xl font-bold tracking-tight">Settings</h1>
		<p class="text-muted-foreground">Preferences for your account.</p>
	</header>

	{#if isLoading}
		<div class="flex h-40 items-center justify-center">
			<Loader class="h-8 w-8 animate-spin text-muted-foreground" />
		</div>
	{:else if settings}
		<div class="space-y-6">
			<Card.Root>
				<Card.Header>
					<Card.Title>General</Card.Title>
					<Card.Description>Timezone and default AI provider.</Card.Description>
				</Card.Header>
				<Card.Content class="space-y-4">
					<div class="space-y-2">
						<Label for="timezone">Timezone</Label>
						<Input id="timezone" bind:value={settings.timezone} placeholder="UTC" />
					</div>
					<div class="space-y-2">
						<Label for="provider">Default LLM provider</Label>
						<select
							id="provider"
							bind:value={settings.default_llm_provider}
							class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none"
						>
							{#each PROVIDERS as provider (provider)}
								<option value={provider}>{provider}</option>
							{/each}
						</select>
					</div>
				</Card.Content>
			</Card.Root>

			<Card.Root>
				<Card.Header>
					<Card.Title>Notifications</Card.Title>
					<Card.Description>Where run alerts are delivered.</Card.Description>
				</Card.Header>
				<Card.Content class="space-y-4">
					<div class="flex items-center justify-between">
						<Label for="notify-email">Email</Label>
						<Switch
							id="notify-email"
							checked={settings.notification_preferences.email ?? false}
							onCheckedChange={(v) => (settings!.notification_preferences.email = v)}
						/>
					</div>
					<div class="flex items-center justify-between">
						<Label for="notify-slack">Slack</Label>
						<Switch
							id="notify-slack"
							checked={settings.notification_preferences.slack ?? false}
							onCheckedChange={(v) => (settings!.notification_preferences.slack = v)}
						/>
					</div>
				</Card.Content>
			</Card.Root>

			<div class="flex justify-end">
				<Button onclick={saveSettings} disabled={isSaving}>
					{#if isSaving}
						<Loader class="mr-1 h-4 w-4 animate-spin" />
					{/if}
					Save changes
				</Button>
			</div>
		</div>
	{/if}
</div>
