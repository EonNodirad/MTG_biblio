<script lang="ts">
	import { suggestCards, getCard } from '$lib/api';
	import type { CardSuggestion, CardDetail } from '$lib/api';
	import CardImage from '$lib/components/CardImage.svelte';
	import ManaCost from '$lib/components/ManaCost.svelte';
	import RarityBadge from '$lib/components/RarityBadge.svelte';

	const BASE = '/api';

	interface WishlistEntry {
		id: string;
		card_uuid: string;
		quantity: number;
		notes: string;
		name?: string;
		scryfallId?: string;
		owned?: number;
		missing?: number;
		card?: CardDetail;
	}

	let entries = $state<WishlistEntry[]>([]);
	let loading = $state(true);
	let toast = $state<string | null>(null);

	// Search
	let searchQuery = $state('');
	let suggestions = $state<CardSuggestion[]>([]);
	let showSuggestions = $state(false);
	let highlightedIdx = $state(-1);
	let suggestTimeout: ReturnType<typeof setTimeout> | null = null;

	async function load() {
		loading = true;
		const res = await fetch(`${BASE}/wishlist/check`);
		const raw: WishlistEntry[] = res.ok ? await res.json() : [];
		// Enrich with full card details for images
		entries = await Promise.all(raw.map(async (e) => {
			try {
				const card = await getCard(e.card_uuid);
				return { ...e, card, scryfallId: card.identifiers?.scryfallId ?? undefined };
			} catch { return e; }
		}));
		loading = false;
	}

	async function addEntry(uuid: string) {
		const res = await fetch(`${BASE}/wishlist/`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ card_uuid: uuid, quantity: 1 }),
		});
		if (res.ok) { await load(); showToast('Carte ajoutée à la wishlist !'); }
	}

	async function changeQty(entry: WishlistEntry, delta: number) {
		const next = entry.quantity + delta;
		if (next <= 0) { await remove(entry); return; }
		await fetch(`${BASE}/wishlist/${entry.id}`, {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ quantity: next }),
		});
		entries = entries.map(e => e.id === entry.id ? { ...e, quantity: next } : e);
	}

	async function updateNotes(entry: WishlistEntry, notes: string) {
		await fetch(`${BASE}/wishlist/${entry.id}`, {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ notes }),
		});
		entries = entries.map(e => e.id === entry.id ? { ...e, notes } : e);
	}

	async function remove(entry: WishlistEntry) {
		await fetch(`${BASE}/wishlist/${entry.id}`, { method: 'DELETE' });
		entries = entries.filter(e => e.id !== entry.id);
	}

	function showToast(msg: string) {
		toast = msg;
		setTimeout(() => (toast = null), 2500);
	}

	function onSearchInput() {
		highlightedIdx = -1;
		if (suggestTimeout) clearTimeout(suggestTimeout);
		if (searchQuery.length < 2) { suggestions = []; showSuggestions = false; return; }
		suggestTimeout = setTimeout(async () => {
			suggestions = await suggestCards(searchQuery, 8);
			showSuggestions = suggestions.length > 0;
		}, 220);
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'ArrowDown') { e.preventDefault(); highlightedIdx = Math.min(highlightedIdx + 1, suggestions.length - 1); }
		else if (e.key === 'ArrowUp') { e.preventDefault(); highlightedIdx = Math.max(highlightedIdx - 1, -1); }
		else if (e.key === 'Enter' && highlightedIdx >= 0 && suggestions[highlightedIdx]) {
			pick(suggestions[highlightedIdx]);
		}
		else if (e.key === 'Escape') showSuggestions = false;
	}

	function pick(s: CardSuggestion) {
		searchQuery = '';
		showSuggestions = false;
		addEntry(s.uuid);
	}

	const totalMissing = $derived(entries.reduce((s, e) => s + (e.missing ?? 0), 0));

	load();
</script>

<div class="space-y-6">

	<!-- Header -->
	<div class="flex items-center justify-between flex-wrap gap-3">
		<div>
			<h1 class="text-2xl font-bold text-amber-400">Wishlist</h1>
			<p class="text-sm text-gray-500 mt-0.5">Cartes désirées — {entries.length} carte(s){totalMissing > 0 ? `, ${totalMissing} à acquérir` : ''}</p>
		</div>
	</div>

	<!-- Search to add -->
	<div class="relative max-w-md">
		<input
			bind:value={searchQuery}
			oninput={onSearchInput}
			onkeydown={onKeydown}
			onfocus={() => searchQuery.length >= 2 && suggestions.length > 0 && (showSuggestions = true)}
			onblur={() => setTimeout(() => (showSuggestions = false), 150)}
			type="text"
			placeholder="Ajouter une carte à la wishlist..."
			class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-amber-500 text-sm"
			autocomplete="off"
		/>
		{#if showSuggestions}
			<ul class="absolute z-50 top-full mt-1 left-0 right-0 bg-gray-800 border border-gray-700 rounded-xl shadow-2xl overflow-hidden">
				{#each suggestions as s, i}
					<li>
						<button onmousedown={() => pick(s)}
							class="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-gray-700 transition-colors {i === highlightedIdx ? 'bg-gray-700' : ''}">
							<CardImage scryfallId={s.scryfallId} size="small" alt={s.name} class="w-8 h-11 rounded object-cover shrink-0" />
							<div class="flex-1 min-w-0">
								{#if s.foreignName}
									<span class="text-white text-sm font-medium">{s.foreignName}</span>
									<span class="text-gray-400 text-xs ml-1">({s.name})</span>
								{:else}
									<span class="text-white text-sm font-medium">{s.name}</span>
								{/if}
								<p class="text-xs text-gray-500 font-mono">{s.setCode}</p>
							</div>
						</button>
					</li>
				{/each}
			</ul>
		{/if}
	</div>

	{#if loading}
		<div class="text-center py-16 text-gray-400">Chargement...</div>
	{:else if entries.length === 0}
		<div class="text-center py-16 text-gray-500">
			Ta wishlist est vide. Recherche une carte ci-dessus pour l'ajouter.
		</div>
	{:else}
		<div class="space-y-2">
			{#each entries as entry (entry.id)}
				{@const isMissing = (entry.missing ?? 0) > 0}
				<div class="bg-gray-800 border {isMissing ? 'border-red-900' : 'border-green-900'} rounded-xl px-4 py-3 flex flex-wrap items-center gap-3">

					<!-- Thumbnail -->
					{#if entry.scryfallId}
						<a href="/cards/{entry.card_uuid}" class="shrink-0">
							<CardImage scryfallId={entry.scryfallId} size="art_crop" alt={entry.name ?? ''} class="w-14 h-10 rounded object-cover" />
						</a>
					{/if}

					<!-- Name + info -->
					<div class="flex-1 min-w-40">
						<a href="/cards/{entry.card_uuid}" class="font-semibold text-white hover:text-amber-400 transition-colors">
							{entry.name ?? entry.card_uuid}
						</a>
						{#if entry.card}
							<div class="flex items-center gap-2 mt-0.5">
								<span class="text-xs text-gray-500 font-mono">{entry.card.setCode}</span>
								<RarityBadge rarity={entry.card.rarity} />
								<ManaCost cost={entry.card.manaCost} />
							</div>
						{/if}
					</div>

					<!-- Owned status -->
					<div class="text-xs px-2 py-1 rounded-lg {isMissing ? 'bg-red-900/40 text-red-400' : 'bg-green-900/40 text-green-400'}">
						{isMissing ? `${entry.owned ?? 0}/${entry.quantity} possédée(s)` : '✓ Possédée'}
					</div>

					<!-- Quantity -->
					<div class="flex items-center gap-2">
						<button onclick={() => changeQty(entry, -1)}
							class="w-7 h-7 rounded-full bg-gray-700 hover:bg-gray-600 text-white font-bold text-lg leading-none flex items-center justify-center">−</button>
						<span class="w-6 text-center font-semibold text-white">{entry.quantity}</span>
						<button onclick={() => changeQty(entry, +1)}
							class="w-7 h-7 rounded-full bg-gray-700 hover:bg-gray-600 text-white font-bold text-lg leading-none flex items-center justify-center">+</button>
					</div>

					<!-- Notes -->
					<input
						value={entry.notes}
						onchange={(e) => updateNotes(entry, (e.target as HTMLInputElement).value)}
						type="text"
						placeholder="Notes..."
						class="text-xs px-2 py-1 bg-gray-700 border border-gray-600 rounded-lg text-gray-300 placeholder-gray-500 focus:outline-none focus:border-amber-500 w-32"
					/>

					<!-- Delete -->
					<button onclick={() => remove(entry)} class="text-gray-500 hover:text-red-400 transition-colors text-sm" title="Supprimer">✕</button>
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
