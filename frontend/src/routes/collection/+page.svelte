<script lang="ts">
	import {
		getCollection,
		getCard,
		updateCollectionEntry,
		removeFromCollection,
		getMissingCards
	} from '$lib/api';
	import type { CollectionEntry, CardDetail } from '$lib/api';
	import RarityBadge from '$lib/components/RarityBadge.svelte';
	import ManaCost from '$lib/components/ManaCost.svelte';
	import CardImage from '$lib/components/CardImage.svelte';

	type EnrichedEntry = CollectionEntry & { card?: CardDetail };

	let entries: EnrichedEntry[] = $state([]);
	let loading = $state(true);
	let filter = $state('');
	let missingSetCode = $state('');
	let missingResult: any = $state(null);
	let loadingMissing = $state(false);
	let toast = $state<string | null>(null);

	const conditions = ['NM', 'LP', 'MP', 'HP', 'DMG'];
	const conditionColors: Record<string, string> = {
		NM:  'bg-green-700 text-green-100 border-green-600',
		LP:  'bg-lime-700 text-lime-100 border-lime-600',
		MP:  'bg-yellow-700 text-yellow-100 border-yellow-600',
		HP:  'bg-orange-700 text-orange-100 border-orange-600',
		DMG: 'bg-red-800 text-red-100 border-red-700',
	};
	const conditionInactive = 'bg-gray-700 text-gray-500 border-gray-600 hover:bg-gray-600';

	async function load() {
		loading = true;
		const raw = await getCollection();
		// Enrich with card details (batched)
		entries = await Promise.all(
			raw.map(async (e) => {
				try {
					const card = await getCard(e.card_uuid);
					return { ...e, card };
				} catch {
					return { ...e };
				}
			})
		);
		loading = false;
	}

	const filtered = $derived(
		filter
			? entries.filter((e) =>
					e.card?.name?.toLowerCase().includes(filter.toLowerCase())
			  )
			: entries
	);

	async function changeQty(entry: EnrichedEntry, delta: number) {
		const newQty = Math.max(0, entry.quantity + delta);
		if (newQty === 0) {
			await removeFromCollection(entry.id);
			entries = entries.filter((e) => e.id !== entry.id);
		} else {
			await updateCollectionEntry(entry.id, { quantity: newQty });
			entries = entries.map((e) => (e.id === entry.id ? { ...e, quantity: newQty } : e));
		}
	}

	async function toggleFoil(entry: EnrichedEntry) {
		await updateCollectionEntry(entry.id, { foil: !entry.foil });
		entries = entries.map((e) => (e.id === entry.id ? { ...e, foil: !e.foil } : e));
	}

	async function changeCondition(entry: EnrichedEntry, condition: string) {
		await updateCollectionEntry(entry.id, { condition });
		entries = entries.map((e) => (e.id === entry.id ? { ...e, condition } : e));
	}

	async function remove(entry: EnrichedEntry) {
		await removeFromCollection(entry.id);
		entries = entries.filter((e) => e.id !== entry.id);
		showToast('Carte supprimée.');
	}

	async function searchMissing() {
		if (!missingSetCode.trim()) return;
		loadingMissing = true;
		try {
			missingResult = await getMissingCards(missingSetCode.trim().toUpperCase());
		} catch (e: any) {
			missingResult = { error: e.message };
		} finally {
			loadingMissing = false;
		}
	}

	function showToast(msg: string) {
		toast = msg;
		setTimeout(() => (toast = null), 2500);
	}

	async function importCsv(e: Event) {
		const file = (e.target as HTMLInputElement).files?.[0];
		if (!file) return;
		const text = await file.text();
		const res = await fetch('/api/collection/import/csv', {
			method: 'POST',
			headers: { 'Content-Type': 'text/plain' },
			body: text,
		});
		const result = await res.json();
		showToast(`${result.imported} carte(s) importée(s)${result.skipped.length ? `, ${result.skipped.length} ignorée(s)` : ''}`);
		await load();
		(e.target as HTMLInputElement).value = '';
	}

	load();
</script>

<div class="space-y-8">
	<div class="flex items-center justify-between flex-wrap gap-3">
		<div>
			<h1 class="text-2xl font-bold text-amber-400">Ma collection</h1>
			<span class="text-sm text-gray-400">{entries.length} carte(s)</span>
		</div>
		<div class="flex gap-2 flex-wrap">
			<a href="/api/collection/export/csv" download="collection.csv"
				class="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg transition-colors">
				↓ Export CSV
			</a>
			<label class="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg transition-colors cursor-pointer">
				↑ Import CSV
				<input type="file" accept=".csv" class="hidden" onchange={importCsv} />
			</label>
		</div>
	</div>

	<!-- Filter -->
	<input
		bind:value={filter}
		type="text"
		placeholder="Filtrer par nom..."
		class="w-full max-w-sm px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-amber-500"
	/>

	{#if loading}
		<div class="text-center py-16 text-gray-400">Chargement...</div>
	{:else if entries.length === 0}
		<div class="text-center py-16 text-gray-500">
			Votre collection est vide. <a href="/cards" class="text-amber-400 hover:underline">Parcourez les cartes</a> pour en ajouter.
		</div>
	{:else}
		<div class="space-y-2">
			{#each filtered as entry (entry.id)}
				<div class="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 flex flex-wrap items-center gap-3">
					<!-- Thumbnail -->
					{#if entry.card?.identifiers?.scryfallId}
						<a href="/cards/{entry.card_uuid}" class="shrink-0">
							<CardImage
								scryfallId={entry.card.identifiers.scryfallId}
								size="art_crop"
								alt={entry.card.name}
								class="w-14 h-10 rounded object-cover"
							/>
						</a>
					{/if}
					<!-- Name + type -->
					<div class="flex-1 min-w-40">
						<a
							href="/cards/{entry.card_uuid}"
							class="font-semibold text-white hover:text-amber-400 transition-colors"
						>
							{entry.card?.name ?? entry.card_uuid}
						</a>
						{#if entry.card}
							<div class="flex items-center gap-2 mt-0.5">
								<span class="text-xs text-gray-500 font-mono">{entry.card.setCode}</span>
								<RarityBadge rarity={entry.card.rarity} />
								<ManaCost cost={entry.card.manaCost} />
							</div>
						{/if}
					</div>

					<!-- Foil toggle -->
					<button
						onclick={() => toggleFoil(entry)}
						class="text-xs px-2 py-1 rounded transition-colors
							{entry.foil ? 'bg-purple-800 text-purple-200' : 'bg-gray-700 text-gray-400 hover:bg-gray-600'}"
					>
						✨ Foil
					</button>

					<!-- Condition -->
					<div class="flex gap-1">
						{#each conditions as c}
							<button
								onclick={() => changeCondition(entry, c)}
								class="text-xs px-2 py-1 rounded border font-medium transition-colors
									{entry.condition === c ? conditionColors[c] : conditionInactive}"
							>{c}</button>
						{/each}
					</div>

					<!-- Quantity controls -->
					<div class="flex items-center gap-2">
						<button
							onclick={() => changeQty(entry, -1)}
							class="w-7 h-7 rounded-full bg-gray-700 hover:bg-gray-600 text-white font-bold text-lg leading-none flex items-center justify-center"
						>−</button>
						<span class="w-6 text-center font-semibold text-white">{entry.quantity}</span>
						<button
							onclick={() => changeQty(entry, +1)}
							class="w-7 h-7 rounded-full bg-gray-700 hover:bg-gray-600 text-white font-bold text-lg leading-none flex items-center justify-center"
						>+</button>
					</div>

					<!-- Delete -->
					<button
						onclick={() => remove(entry)}
						class="text-gray-500 hover:text-red-400 transition-colors text-sm"
						title="Supprimer"
					>✕</button>
				</div>
			{/each}
		</div>
	{/if}

	<!-- Missing cards section -->
	<div class="border-t border-gray-800 pt-6 space-y-4">
		<h2 class="text-lg font-semibold text-gray-300">Cartes manquantes par set</h2>
		<div class="flex gap-3">
			<input
				bind:value={missingSetCode}
				type="text"
				placeholder="Code du set (ex: MH2)"
				class="w-48 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-amber-500 uppercase"
			/>
			<button
				onclick={searchMissing}
				disabled={loadingMissing}
				class="px-5 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-gray-950 font-semibold rounded-lg transition-colors"
			>
				{loadingMissing ? '...' : 'Analyser'}
			</button>
		</div>

		{#if missingResult?.error}
			<p class="text-red-400 text-sm">{missingResult.error}</p>
		{:else if missingResult}
			<div class="bg-gray-800 border border-gray-700 rounded-xl p-4 space-y-3">
				<div class="flex gap-6 text-sm">
					<span class="text-gray-400">Set : <span class="text-white font-mono">{missingResult.set}</span></span>
					<span class="text-gray-400">Total : <span class="text-white">{missingResult.total}</span></span>
					<span class="text-gray-400">Manquantes : <span class="text-red-400 font-semibold">{missingResult.missing_count}</span></span>
					<span class="text-gray-400">Complété : <span class="text-green-400 font-semibold">{Math.round(((missingResult.total - missingResult.missing_count) / missingResult.total) * 100)}%</span></span>
				</div>
				{#if missingResult.missing.length > 0}
					<div class="max-h-64 overflow-y-auto space-y-1">
						{#each missingResult.missing as card}
							<div class="flex items-center gap-3 text-sm">
								<a href="/cards/{card.uuid}" class="text-white hover:text-amber-400">{card.name}</a>
								<RarityBadge rarity={card.rarity} />
								<ManaCost cost={card.manaCost} />
							</div>
						{/each}
					</div>
				{/if}
			</div>
		{/if}
	</div>
</div>

{#if toast}
	<div class="fixed bottom-6 right-6 bg-gray-700 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-medium">
		{toast}
	</div>
{/if}
