<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';

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
	</nav>

	<main class="max-w-7xl mx-auto px-4 py-6">
		{@render children()}
	</main>
</div>
