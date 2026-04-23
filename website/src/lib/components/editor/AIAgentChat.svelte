<script lang="ts">
    import { Send, Bot, X, Loader2, Sparkles } from 'lucide-svelte';
    import { Button } from '$lib/components/ui/button';
    import { api } from '$lib/api/client';
    import { slide, fade } from 'svelte/transition';

    let { onAIUpdate, getCurrentConfig } = $props();

    let isOpen = $state(false);
    let prompt = $state('');
    let isLoading = $state(false);
    let messages = $state<{role: 'user' | 'ai', content: string}[]>([
        { role: 'ai', content: 'Hi! Describe how you want to modify or create your workflow.' }
    ]);

    // Auto-scroll reference
    let chatContainer: HTMLElement;

    function scrollToBottom() {
        setTimeout(() => {
            if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
        }, 50);
    }

    async function handleSubmit() {
        if (!prompt.trim() || isLoading) return;

        const userText = prompt;
        messages = [...messages, { role: 'user', content: userText }];
        prompt = '';
        isLoading = true;
        scrollToBottom();

        try {
            const currentWorkflow = getCurrentConfig();
            
            const res = await api.post('/api/ai/interpret', {
                text: userText,
                current_workflow: currentWorkflow
            });

            if (res.success && res.data) {
                messages = [...messages, { role: 'ai', content: 'Workflow updated successfully!' }];
                onAIUpdate(res.data); 
            } else {
                messages = [...messages, { role: 'ai', content: res.error || 'Failed to update workflow.' }];
            }
        } catch (error) {
            messages = [...messages, { role: 'ai', content: 'An error occurred while connecting to the AI.' }];
        } finally {
            isLoading = false;
            scrollToBottom();
        }
    }
</script>

<div class="absolute bottom-6 right-6 z-50 flex flex-col items-end gap-4">
    {#if isOpen}
        <div 
            transition:slide={{ duration: 200 }}
            class="flex h-96 w-80 flex-col overflow-hidden rounded-xl border bg-card shadow-2xl"
        >
            <div class="flex items-center justify-between border-b bg-primary/10 p-3">
                <div class="flex items-center gap-2 font-semibold">
                    <Sparkles size={16} class="text-primary" /> 
                    <span>AI Co-Pilot</span>
                </div>
                <Button variant="ghost" size="icon" class="h-6 w-6" onclick={() => (isOpen = false)}>
                    <X size={16} />
                </Button>
            </div>
            
            <div bind:this={chatContainer} class="flex grow flex-col gap-3 overflow-y-auto p-4">
                {#each messages as msg}
                    <div class="flex w-full {msg.role === 'user' ? 'justify-end' : 'justify-start'}">
                        <div class="max-w-[85%] rounded-lg p-2.5 text-sm {msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'}">
                            {msg.content}
                        </div>
                    </div>
                {/each}
                {#if isLoading}
                    <div class="flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2 class="animate-spin" size={14} /> Thinking...
                    </div>
                {/if}
            </div>

            <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="flex items-center gap-2 border-t p-3">
                <input 
                    type="text" 
                    bind:value={prompt} 
                    placeholder="E.g., Add a slack alert..." 
                    class="grow rounded-md bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                    disabled={isLoading}
                />
                <Button type="submit" size="icon" variant="default" class="h-8 w-8 rounded-full" disabled={isLoading || !prompt.trim()}>
                    <Send size={14} />
                </Button>
            </form>
        </div>
    {/if}

    {#if !isOpen}
        <Button 
            onclick={() => (isOpen = true)}
            size="icon" 
            class="h-14 w-14 rounded-full shadow-lg hover:shadow-xl hover:scale-105 transition-all"
        >
            <Bot size={28} />
        </Button>
    {/if}
</div>
