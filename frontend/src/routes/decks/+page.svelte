<script lang="ts">
	import { listDecks, createDeck, deleteDeck, updateDeck } from '$lib/api';
	import type { Deck } from '$lib/api';
	import { toast } from '$lib/toast.svelte';

	let decks: Deck[] = $state([]);
	let loading = $state(true);
	let showForm = $state(false);
	let newName = $state('');
	let newDesc = $state('');
	let newFormat = $state('');
	let newColors = $state<string[]>([]);
	let creating = $state(false);

	// Edit state
	let editingId = $state<string | null>(null);
	let editName = $state('');
	let editFormat = $state('');
	let editColors = $state<string[]>([]);
	let saving = $state(false);

	const formats = ['', 'Standard', 'Pioneer', 'Modern', 'Legacy', 'Vintage', 'Commander', 'Draft'];
	const MANA_COLORS = ['W', 'U', 'B', 'R', 'G'];
	const COLOR_LABELS: Record<string, string> = { W: 'Blanc', U: 'Bleu', B: 'Noir', R: 'Rouge', G: 'Vert' };

	function manaSymbolUrl(sym: string) {
		return `https://svgs.scryfall.io/card-symbols/${sym}.svg`;
	}

	function parseColors(colorsStr: string): string[] {
		if (!colorsStr) return [];
		return colorsStr.split(',').filter(Boolean);
	}

	function toggleColor(color: string, arr: string[]): string[] {
		return arr.includes(color) ? arr.filter((c) => c !== color) : [...arr, color];
	}

	function colorsToString(arr: string[]): string {
		// Keep canonical WUBRG order
		return MANA_COLORS.filter((c) => arr.includes(c)).join(',');
	}

	async function load() {
		loading = true;
		decks = await listDecks();
		loading = false;
	}

	async function create() {
		if (!newName.trim()) return;
		creating = true;
		try {
			const deck = await createDeck({
				name: newName,
				description: newDesc,
				format: newFormat,
				colors: colorsToString(newColors)
			});
			decks = [...decks, deck];
			newName = '';
			newDesc = '';
			newFormat = '';
			newColors = [];
			showForm = false;
			toast.success('Deck créé !');
		} finally {
			creating = false;
		}
	}

	async function remove(id: string) {
		await deleteDeck(id);
		decks = decks.filter((d) => d.id !== id);
		toast.success('Deck supprimé.');
	}

	function startEdit(deck: Deck) {
		editingId = deck.id;
		editName = deck.name;
		editFormat = deck.format;
		editColors = parseColors(deck.colors);
	}

	function cancelEdit() {
		editingId = null;
	}

	async function saveEdit() {
		if (!editingId || !editName.trim()) return;
		saving = true;
		try {
			const updated = await updateDeck(editingId, {
				name: editName,
				format: editFormat,
				colors: colorsToString(editColors)
			});
			decks = decks.map((d) => (d.id === editingId ? { ...d, ...updated } : d));
			editingId = null;
			toast.success('Deck mis à jour.');
		} finally {
			saving = false;
		}
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
			<!-- Color picker -->
			<div>
				<p class="text-xs text-gray-400 mb-2">Couleurs</p>
				<div class="flex gap-2">
					{#each MANA_COLORS as c}
						<button
							onclick={() => (newColors = toggleColor(c, newColors))}
							title={COLOR_LABELS[c]}
							class="w-8 h-8 rounded-full border-2 transition-all {newColors.includes(c) ? 'border-amber-400 scale-110' : 'border-gray-600 opacity-50 hover:opacity-80'}"
						>
							<img src={manaSymbolUrl(c)} alt={c} class="w-full h-full rounded-full" />
						</button>
					{/each}
				</div>
			</div>
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
					{#if editingId === deck.id}
						<!-- Inline edit form -->
						<div class="space-y-2">
							<input
								bind:value={editName}
								type="text"
								placeholder="Nom *"
								class="w-full px-3 py-1.5 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:border-amber-500"
							/>
							<select
								bind:value={editFormat}
								class="w-full px-3 py-1.5 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:border-amber-500"
							>
								{#each formats as f}
									<option value={f}>{f || 'Format (optionnel)'}</option>
								{/each}
							</select>
							<div>
								<p class="text-xs text-gray-400 mb-1">Couleurs</p>
								<div class="flex gap-1.5">
									{#each MANA_COLORS as c}
										<button
											onclick={() => (editColors = toggleColor(c, editColors))}
											title={COLOR_LABELS[c]}
											class="w-7 h-7 rounded-full border-2 transition-all {editColors.includes(c) ? 'border-amber-400 scale-110' : 'border-gray-600 opacity-50 hover:opacity-80'}"
										>
											<img src={manaSymbolUrl(c)} alt={c} class="w-full h-full rounded-full" />
										</button>
									{/each}
								</div>
							</div>
							<div class="flex gap-2 pt-1">
								<button
									onclick={saveEdit}
									disabled={saving || !editName.trim()}
									class="flex-1 py-1.5 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-gray-950 font-semibold rounded-lg text-sm transition-colors"
								>
									{saving ? '...' : 'Enregistrer'}
								</button>
								<button
									onclick={cancelEdit}
									class="flex-1 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg text-sm transition-colors"
								>
									Annuler
								</button>
							</div>
						</div>
					{:else}
						<!-- Normal view -->
						<div class="flex items-start justify-between gap-2">
							<div class="min-w-0">
								<h2 class="font-semibold text-white truncate">{deck.name}</h2>
								<div class="flex items-center gap-2 flex-wrap mt-0.5">
									{#if deck.format}
										<span class="text-xs text-amber-400">{deck.format}</span>
									{/if}
									{#if deck.colors}
										<div class="flex gap-1">
											{#each parseColors(deck.colors) as c}
												<img src={manaSymbolUrl(c)} alt={c} class="w-4 h-4 rounded-full" />
											{/each}
										</div>
									{/if}
								</div>
							</div>
							<div class="flex gap-1 shrink-0">
								<button
									onclick={() => startEdit(deck)}
									class="text-gray-500 hover:text-amber-400 transition-colors text-sm p-0.5"
									title="Modifier"
								>✏</button>
								<button
									onclick={() => remove(deck.id)}
									class="text-gray-500 hover:text-red-400 transition-colors text-sm p-0.5"
									title="Supprimer"
								>✕</button>
							</div>
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
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>
