<script lang="ts">
	import { listDecks, createDeck, deleteDeck } from '$lib/api';
	import type { Deck } from '$lib/api';

	let decks: Deck[] = $state([]);
	let loading = $state(true);
	let showForm = $state(false);
	let newName = $state('');
	let newDesc = $state('');
	let newFormat = $state('');
	let creating = $state(false);
	let toast = $state<string | null>(null);

	const formats = ['', 'Standard', 'Pioneer', 'Modern', 'Legacy', 'Vintage', 'Commander', 'Draft'];

	async function load() {
		loading = true;
		decks = await listDecks();
		loading = false;
	}

	async function create() {
		if (!newName.trim()) return;
		creating = true;
		const deck = await createDeck({ name: newName, description: newDesc, format: newFormat });
		decks = [...decks, deck];
		newName = '';
		newDesc = '';
		newFormat = '';
		showForm = false;
		creating = false;
		showToast('Deck créé !');
	}

	async function remove(id: string) {
		await deleteDeck(id);
		decks = decks.filter((d) => d.id !== id);
		showToast('Deck supprimé.');
	}

	function showToast(msg: string) {
		toast = msg;
		setTimeout(() => (toast = null), 2500);
	}

	load();
</script>

<div class="space-y-6">
	<div class="flex items-center justify-between">
		<h1 class="text-2xl font-bold text-amber-400">Mes decks</h1>
		<button
			onclick={() => (showForm = !showForm)}
			class="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-gray-950 font-semibold rounded-lg text-sm transition-colors"
		>
			{showForm ? 'Annuler' : '+ Nouveau deck'}
		</button>
	</div>

	{#if showForm}
		<div class="bg-gray-800 border border-gray-700 rounded-xl p-5 space-y-3 max-w-lg">
			<h2 class="font-semibold text-white">Nouveau deck</h2>
			<input
				bind:value={newName}
				type="text"
				placeholder="Nom du deck *"
				class="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-amber-500"
			/>
			<textarea
				bind:value={newDesc}
				placeholder="Description (optionnel)"
				rows="2"
				class="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-amber-500 resize-none"
			></textarea>
			<select
				bind:value={newFormat}
				class="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-amber-500"
			>
				{#each formats as f}
					<option value={f}>{f || 'Format (optionnel)'}</option>
				{/each}
			</select>
			<button
				onclick={create}
				disabled={creating || !newName.trim()}
				class="w-full py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-gray-950 font-semibold rounded-lg transition-colors"
			>
				{creating ? 'Création...' : 'Créer'}
			</button>
		</div>
	{/if}

	{#if loading}
		<div class="text-center py-16 text-gray-400">Chargement...</div>
	{:else if decks.length === 0}
		<div class="text-center py-16 text-gray-500">
			Aucun deck. Créez-en un pour commencer !
		</div>
	{:else}
		<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
			{#each decks as deck (deck.id)}
				<div class="bg-gray-800 border border-gray-700 rounded-xl p-5 flex flex-col gap-3 hover:border-amber-600 transition-colors">
					<div class="flex items-start justify-between gap-2">
						<div>
							<h2 class="font-semibold text-white">{deck.name}</h2>
							{#if deck.format}
								<span class="text-xs text-amber-400">{deck.format}</span>
							{/if}
						</div>
						<button
							onclick={() => remove(deck.id)}
							class="text-gray-500 hover:text-red-400 transition-colors text-sm shrink-0"
							title="Supprimer"
						>✕</button>
					</div>
					{#if deck.description}
						<p class="text-sm text-gray-400 line-clamp-2">{deck.description}</p>
					{/if}
					<div class="text-xs text-gray-500 mt-auto">{deck.entries.length} carte(s)</div>
					<a
						href="/decks/{deck.id}"
						class="block text-center py-2 bg-gray-700 hover:bg-amber-600 hover:text-white text-gray-300 rounded-lg text-sm font-medium transition-colors"
					>
						Ouvrir le deck →
					</a>
				</div>
			{/each}
		</div>
	{/if}
</div>

{#if toast}
	<div class="fixed bottom-6 right-6 bg-gray-700 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-medium">
		{toast}
	</div>
{/if}
