<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import { toast } from '$lib/toast.svelte';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>MTG Collection</title>
</svelte:head>

<div class="min-h-screen bg-gray-950 text-gray-100">
	<nav class="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center gap-6">
		<a href="/" class="text-lg font-bold text-amber-400 tracking-wide">MTG Collection</a>
		<a href="/cards" class="text-sm text-gray-300 hover:text-white transition-colors">Cartes</a>
		<a href="/collection" class="text-sm text-gray-300 hover:text-white transition-colors">Collection</a>
		<a href="/decks" class="text-sm text-gray-300 hover:text-white transition-colors">Decks</a>
		<a href="/wishlist" class="text-sm text-gray-300 hover:text-white transition-colors">Wishlist</a>
		<a href="/scan" class="text-sm text-gray-300 hover:text-white transition-colors">Scanner</a>
	</nav>

	<main class="max-w-7xl mx-auto px-4 py-6">
		{@render children()}
	</main>
</div>

{#if toast.current}
	{@const t = toast.current}
	<div class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-5 py-3 rounded-xl shadow-2xl text-sm font-medium transition-all
		{t.type === 'loading' ? 'bg-orange-600 text-white' : t.type === 'success' ? 'bg-green-700 text-white' : 'bg-red-700 text-white'}">
		{#if t.type === 'loading'}
			<svg class="animate-spin h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
			</svg>
		{:else if t.type === 'success'}
			<svg class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
				<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
			</svg>
		{/if}
		{t.message}
	</div>
{/if}
