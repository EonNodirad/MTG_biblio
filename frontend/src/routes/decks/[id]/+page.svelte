<script lang="ts">
	import { page } from '$app/state';
	import {
		getDeck, getDeckFeasibility, getDeckPrice,
		addCardToDeck, removeCardFromDeck, updateDeckEntry, moveDeckEntry,
		importDeckText, exportDeckText,
		searchCards, suggestCards, getCard
	} from '$lib/api';
	import type { Deck, FeasibilityResult, DeckPrice, CardSummary, CardDetail, CardSuggestion } from '$lib/api';
	import ManaCost from '$lib/components/ManaCost.svelte';
	import RarityBadge from '$lib/components/RarityBadge.svelte';
	import CardImage from '$lib/components/CardImage.svelte';
	import DeckStats from '$lib/components/DeckStats.svelte';
	import DeckCardModal from '$lib/components/DeckCardModal.svelte';

	const DECK_SECTIONS = new Set<string>(['mainboard', 'sideboard', 'commander', 'companion', 'maybeboard']);

	const deckId = $derived(page.params.id ?? '');

	let deck: Deck | null = $state(null);
	let feasibility: FeasibilityResult | null = $state(null);
	let deckPrice: DeckPrice | null = $state(null);
	let loading = $state(true);
	let activeTab = $state<'mainboard' | 'sideboard' | 'maybeboard'>('mainboard');
	let viewMode = $state<'list' | 'grid'>('grid');
	let groupBy = $state<'category' | 'deck_category' | 'type' | 'cmc' | 'color' | 'rarity'>('deck_category');
	let hoveredCard = $state<string | null>(null);
	let toast = $state<string | null>(null);

	// uuid → card info cache
	let cardCache: Record<string, CardDetail> = $state({});

	// Card modal
	let modalEntryId = $state<string | null>(null);
	const modalEntry = $derived(deck?.entries.find((e) => e.id === modalEntryId) ?? null);
	const modalCard  = $derived(modalEntry ? cardCache[modalEntry.card_uuid] : undefined);

	// Search / autocomplete
	let showSearch = $state(false);
	let addCategory = $state('auto');
	let searchQuery = $state('');
	let searchResults: CardSummary[] = $state([]);
	let searching = $state(false);
	let suggestions: CardSuggestion[] = $state([]);
	let showSuggestions = $state(false);
	let highlightedIdx = $state(-1);
	let suggestTimeout: ReturnType<typeof setTimeout> | null = null;

	// Import / Export
	let showImport = $state(false);
	let importText = $state('');
	let importing = $state(false);
	let importResult = $state<{ imported: number; skipped: string[] } | null>(null);
	let showExport = $state(false);
	let exportText = $state('');

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function load() {
		loading = true;
		[deck, feasibility, deckPrice] = await Promise.all([getDeck(deckId), getDeckFeasibility(deckId), getDeckPrice(deckId).catch(() => null)]);
		await enrichCards();
		loading = false;
	}

	async function enrichCards() {
		if (!deck) return;
		const uuids = [...new Set(deck.entries.map((e) => e.card_uuid))].filter((u) => !cardCache[u]);
		const fetched = await Promise.all(uuids.map((u) => getCard(u).catch(() => null)));
		const update: Record<string, CardDetail> = {};
		uuids.forEach((u, i) => { if (fetched[i]) update[u] = fetched[i]!; });
		cardCache = { ...cardCache, ...update };
	}

	async function reload() {
		[deck, feasibility, deckPrice] = await Promise.all([getDeck(deckId), getDeckFeasibility(deckId), getDeckPrice(deckId).catch(() => null)]);
		await enrichCards();
	}

	// -----------------------------------------------------------------------
	// Card mutations
	// -----------------------------------------------------------------------

	function typeCategory(type: string): string {
		return TYPE_GROUPS.find((g) => g.test(type))?.label ?? 'Autres';
	}

	async function addCard(card: CardSummary) {
		if (!deck) return;
		const cat = addCategory === 'auto' ? typeCategory(card.type) : addCategory;
		await addCardToDeck(deckId, { card_uuid: card.uuid, category: cat });
		await reload();
		showToast(`${card.name} ajouté en ${cat} !`);
	}

	async function removeCard(entryId: string) {
		await removeCardFromDeck(deckId, entryId);
		await reload();
	}

	async function changeQty(entryId: string, delta: number, current: number) {
		const next = current + delta;
		if (next <= 0) await removeCardFromDeck(deckId, entryId);
		else await updateDeckEntry(deckId, entryId, next);
		await reload();
	}

	async function modalChangeQty(delta: number) {
		if (!modalEntry) return;
		const next = modalEntry.quantity + delta;
		if (next <= 0) { await removeCardFromDeck(deckId, modalEntry.id); modalEntryId = null; }
		else await updateDeckEntry(deckId, modalEntry.id, next);
		await reload();
	}

	async function modalChangeCategory(category: string) {
		if (!modalEntry || modalEntry.category === category) return;
		await moveDeckEntry(deckId, modalEntry.id, category);
		await reload();
	}

	async function modalDelete() {
		if (!modalEntry) return;
		await removeCardFromDeck(deckId, modalEntry.id);
		modalEntryId = null;
		await reload();
	}

	// -----------------------------------------------------------------------
	// Search / autocomplete
	// -----------------------------------------------------------------------

	async function search(q = searchQuery) {
		if (!q.trim()) return;
		showSuggestions = false;
		searching = true;
		searchResults = await searchCards({ q, limit: 30 });
		searching = false;
	}

	function onSearchInput() {
		highlightedIdx = -1;
		if (suggestTimeout) clearTimeout(suggestTimeout);
		if (searchQuery.length < 2) { suggestions = []; showSuggestions = false; return; }
		suggestTimeout = setTimeout(async () => {
			suggestions = await suggestCards(searchQuery, 10);
			showSuggestions = suggestions.length > 0;
		}, 220);
	}

	function onSearchKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			if (highlightedIdx >= 0 && suggestions[highlightedIdx]) pickSuggestion(suggestions[highlightedIdx]);
			else search();
		} else if (e.key === 'ArrowDown') { e.preventDefault(); highlightedIdx = Math.min(highlightedIdx + 1, suggestions.length - 1); }
		else if (e.key === 'ArrowUp') { e.preventDefault(); highlightedIdx = Math.max(highlightedIdx - 1, -1); }
		else if (e.key === 'Escape') showSuggestions = false;
	}

	function pickSuggestion(s: CardSuggestion) {
		searchQuery = s.foreignName ?? s.name;
		showSuggestions = false;
		search(searchQuery);
	}

	// -----------------------------------------------------------------------
	// Import / Export
	// -----------------------------------------------------------------------

	async function doImport() {
		if (!importText.trim()) return;
		importing = true;
		importResult = null;
		try {
			importResult = await importDeckText(deckId, importText);
			importText = '';
			await reload();
		} finally { importing = false; }
	}

	async function doExport() {
		exportText = await exportDeckText(deckId);
		showExport = true;
	}

	// -----------------------------------------------------------------------
	// Grouping logic
	// -----------------------------------------------------------------------

	const TYPE_GROUPS = [
		{ label: 'Créatures',           test: (t: string) => t.includes('Creature') },
		{ label: 'Éphémères',           test: (t: string) => t.includes('Instant') },
		{ label: 'Rituels',             test: (t: string) => t.includes('Sorcery') },
		{ label: 'Planeswalkers',       test: (t: string) => t.includes('Planeswalker') },
		{ label: 'Artefacts',           test: (t: string) => t.includes('Artifact') && !t.includes('Creature') },
		{ label: 'Enchantements',       test: (t: string) => t.includes('Enchantment') && !t.includes('Creature') },
		{ label: 'Terrains',            test: (t: string) => t.includes('Land') },
		{ label: 'Autres',              test: () => true },
	];

	const MAIN_TYPES = ['Creature','Instant','Sorcery','Land','Artifact','Enchantment','Planeswalker','Battle'];
	const COLOR_ORDER = ['Blanc','Bleu','Noir','Rouge','Vert','Multicolore','Incolore'];
	const COLOR_NAMES: Record<string, string> = { W:'Blanc', U:'Bleu', B:'Noir', R:'Rouge', G:'Vert' };
	const RARITY_ORDER = ['mythic','rare','uncommon','common','special','bonus'];
	const RARITY_LABELS: Record<string, string> = { mythic:'Mythique', rare:'Rare', uncommon:'Inhabituelle', common:'Commune', special:'Spéciale', bonus:'Bonus' };

	const GROUP_OPTIONS: { mode: typeof groupBy; label: string }[] = [
		{ mode: 'category',      label: 'Catégorie' },
		{ mode: 'deck_category', label: 'Section deck' },
		{ mode: 'type',          label: 'Type' },
		{ mode: 'cmc',           label: 'Mana' },
		{ mode: 'color',         label: 'Couleur' },
		{ mode: 'rarity',        label: 'Rareté' },
	];

	// -----------------------------------------------------------------------
	// Derived state
	// -----------------------------------------------------------------------

	const commander   = $derived(deck?.entries.filter((e) => e.category === 'commander')  ?? []);
	const companion   = $derived(deck?.entries.filter((e) => e.category === 'companion')  ?? []);
	// mainboard = everything that isn't a named deck section (includes custom categories like "Pioche")
	const mainboard   = $derived(deck?.entries.filter((e) => !DECK_SECTIONS.has(e.category) || e.category === 'mainboard') ?? []);
	const sideboard   = $derived(deck?.entries.filter((e) => e.category === 'sideboard')  ?? []);
	const maybeboard  = $derived(deck?.entries.filter((e) => e.category === 'maybeboard') ?? []);

	const totalMain  = $derived(mainboard.reduce((s, e) => s + e.quantity, 0));
	const totalSide  = $derived(sideboard.reduce((s, e) => s + e.quantity, 0));
	const totalMaybe = $derived(maybeboard.reduce((s, e) => s + e.quantity, 0));

	const activeEntries = $derived(
		activeTab === 'sideboard' ? sideboard :
		activeTab === 'maybeboard' ? maybeboard : mainboard
	);

	type Group = { label: string; entries: typeof activeEntries; count: number };

	// Inline in $derived.by so Svelte tracks cardCache and groupBy as dependencies
	const groupedEntries = $derived.by((): Group[] => {
		const entries = activeEntries;
		const cache = cardCache;   // explicit read → tracked
		const mode  = groupBy;     // explicit read → tracked

		type E = (typeof entries)[number];
		function bucket<K extends string | number>(
			keyOf: (e: E) => K,
			order: K[],
			labelOf: (k: K) => string = (k) => String(k)
		): Group[] {
			const map = new Map<K, E[]>();
			for (const e of entries) { const k = keyOf(e); if (!map.has(k)) map.set(k, []); map.get(k)!.push(e); }
			return order.filter((k) => map.has(k)).map((k) => ({
				label: labelOf(k),
				entries: map.get(k)!,
				count: map.get(k)!.reduce((s, e) => s + e.quantity, 0),
			}));
		}

		if (mode === 'deck_category') {
			// Group by the actual entry.category field (custom + predefined)
			const LABEL: Record<string, string> = {
				mainboard: 'Mainboard', sideboard: 'Sideboard',
				commander: 'Commander', companion: 'Compagnon', maybeboard: 'Maybeboard',
			};
			const seen = new Map<string, E[]>();
			for (const e of entries) {
				const k = e.category;
				if (!seen.has(k)) seen.set(k, []);
				seen.get(k)!.push(e);
			}
			return [...seen.entries()].map(([k, es]) => ({
				label: LABEL[k] ?? k,
				entries: es,
				count: es.reduce((s, e) => s + e.quantity, 0),
			}));
		}

		if (mode === 'category') {
			const groups: Group[] = TYPE_GROUPS.map((g) => ({ label: g.label, entries: [], count: 0 }));
			for (const e of entries) {
				const type = cache[e.card_uuid]?.type ?? '';
				const idx = TYPE_GROUPS.findIndex((g) => g.test(type));
				const gi = idx >= 0 ? idx : TYPE_GROUPS.length - 1;
				groups[gi].entries.push(e);
				groups[gi].count += e.quantity;
			}
			return groups.filter((g) => g.entries.length > 0);
		}

		if (mode === 'type') {
			return bucket(
				(e) => MAIN_TYPES.find((t) => (cache[e.card_uuid]?.type ?? '').includes(t)) ?? 'Autre',
				[...MAIN_TYPES, 'Autre']
			);
		}

		if (mode === 'cmc') {
			return bucket(
				(e) => Math.min(Math.round(cache[e.card_uuid]?.manaValue ?? 0), 7),
				[0, 1, 2, 3, 4, 5, 6, 7],
				(k) => k === 7 ? '7+' : String(k)
			);
		}

		if (mode === 'color') {
			return bucket(
				(e) => {
					const ci: string[] = cache[e.card_uuid]?.colorIdentity ?? [];
					if (ci.length === 0) return 'Incolore';
					if (ci.length > 1) return 'Multicolore';
					return COLOR_NAMES[ci[0]] ?? 'Autre';
				},
				COLOR_ORDER
			);
		}

		// rarity
		return bucket(
			(e) => cache[e.card_uuid]?.rarity ?? 'common',
			RARITY_ORDER,
			(k) => RARITY_LABELS[k] ?? k
		);
	});
	const missingUuids = $derived(new Set(feasibility?.missing.map((c) => c.card_uuid) ?? []));
	const feasMap = $derived(new Map<string, { owned: number; needed: number }>(
		[...(feasibility?.missing.map(c => [c.card_uuid, { owned: c.owned, needed: c.needed }] as [string, { owned: number; needed: number }]) ?? []),
		 ...(feasibility?.owned.map(c => [c.card_uuid, { owned: c.owned, needed: c.needed }] as [string, { owned: number; needed: number }]) ?? [])]
	));
	const deckCategories = $derived<string[]>([...new Set(deck?.entries.map((e) => e.category) ?? [])]);

	const isCommander = $derived(
		deck?.format?.toLowerCase().includes('commander') ||
		deck?.format?.toLowerCase().includes('edh') ||
		commander.length > 0
	);

	function showToast(msg: string) {
		toast = msg;
		setTimeout(() => (toast = null), 2000);
	}

	$effect(() => { if (deckId) load(); });
</script>

{#if loading}
	<div class="text-center py-16 text-gray-400">Chargement...</div>
{:else if !deck}
	<div class="text-center py-16 text-red-400">Deck introuvable.</div>
{:else}
<div class="space-y-5">

	<!-- Header -->
	<div class="flex items-start justify-between flex-wrap gap-4">
		<div>
			<a href="/decks" class="text-sm text-gray-500 hover:text-white transition-colors">← Mes decks</a>
			<h1 class="text-2xl font-bold text-white mt-1">{deck.name}</h1>
			<div class="flex items-center gap-3 mt-1 flex-wrap">
				{#if deck.format}<span class="text-sm text-amber-400">{deck.format}</span>{/if}
				{#if deck.description}<span class="text-sm text-gray-400">{deck.description}</span>{/if}
			</div>
		</div>
		<div class="flex items-center gap-2 flex-wrap">
			{#if deckPrice && (deckPrice.total_eur > 0 || deckPrice.total_usd > 0)}
				<div class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-green-800 bg-green-900/20 text-sm text-green-400">
					{#if deckPrice.total_eur > 0}€{deckPrice.total_eur.toFixed(2)}{/if}
					{#if deckPrice.total_eur > 0 && deckPrice.total_usd > 0}<span class="text-green-700">·</span>{/if}
					{#if deckPrice.total_usd > 0}${deckPrice.total_usd.toFixed(2)}{/if}
				</div>
			{/if}
			{#if feasibility}
				<div class="flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm
					{feasibility.feasible ? 'border-green-700 bg-green-900/30 text-green-400' : 'border-red-800 bg-red-900/20 text-red-400'}">
					{feasibility.feasible ? '✓ Réalisable' : `✗ ${feasibility.missing.length} manquante(s)`}
				</div>
			{/if}
			<button onclick={doExport} class="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg transition-colors">
				↓ Exporter
			</button>
		</div>
	</div>

	<!-- Commander / Companion section -->
	{#if isCommander && (commander.length > 0 || companion.length > 0)}
		<div class="space-y-2">
			{#if commander.length > 0}
				<p class="text-xs font-semibold text-amber-500 uppercase tracking-wide">Commandant</p>
				<div class="flex flex-wrap gap-3">
					{#each commander as entry (entry.id)}
						{@const card = cardCache[entry.card_uuid]}
						{@const scryfallId = card?.identifiers?.scryfallId}
						<div class="relative group w-28">
							<a href="/cards/{entry.card_uuid}">
								<CardImage
									{scryfallId}
									size="normal"
									alt={card?.name ?? entry.card_uuid}
									class="w-full rounded-xl ring-2 ring-amber-500 shadow-lg shadow-amber-900/40"
								/>
							</a>
							<p class="text-xs text-center text-amber-300 mt-1 truncate">{card?.name ?? '...'}</p>
							<button
								onclick={() => removeCard(entry.id)}
								class="absolute top-1 right-1 w-5 h-5 bg-gray-900/80 rounded-full text-gray-400 hover:text-red-400 text-xs opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
							>✕</button>
						</div>
					{/each}
					<!-- Add commander slot -->
					{#if commander.length < 2}
						<button
							onclick={() => { addCategory = 'commander'; showSearch = true; showImport = false; }}
							class="w-28 aspect-[488/680] rounded-xl border-2 border-dashed border-amber-700 hover:border-amber-500 text-amber-700 hover:text-amber-500 transition-colors flex items-center justify-center text-2xl"
						>+</button>
					{/if}
				</div>
			{:else if isCommander}
				<div class="flex items-center gap-3">
					<p class="text-xs font-semibold text-amber-500 uppercase tracking-wide">Commandant</p>
					<button
						onclick={() => { addCategory = 'commander'; showSearch = true; showImport = false; }}
						class="text-xs text-amber-600 hover:text-amber-400 transition-colors"
					>+ Ajouter un commandant</button>
				</div>
			{/if}

			{#if companion.length > 0}
				<p class="text-xs font-semibold text-purple-400 uppercase tracking-wide mt-3">Compagnon</p>
				<div class="flex flex-wrap gap-3">
					{#each companion as entry (entry.id)}
						{@const card = cardCache[entry.card_uuid]}
						{@const scryfallId = card?.identifiers?.scryfallId}
						<div class="relative group w-28">
							<a href="/cards/{entry.card_uuid}">
								<CardImage {scryfallId} size="normal" alt={card?.name ?? entry.card_uuid}
									class="w-full rounded-xl ring-2 ring-purple-500" />
							</a>
							<p class="text-xs text-center text-purple-300 mt-1 truncate">{card?.name ?? '...'}</p>
							<button onclick={() => removeCard(entry.id)}
								class="absolute top-1 right-1 w-5 h-5 bg-gray-900/80 rounded-full text-gray-400 hover:text-red-400 text-xs opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">✕</button>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}

	<!-- Main layout -->
	<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

		<!-- Left: deck list -->
		<div class="lg:col-span-2 space-y-3">

			<!-- Tabs + view toggle -->
			<div class="flex items-center justify-between gap-2 flex-wrap">
				<div class="flex gap-2 flex-wrap">
					<button onclick={() => (activeTab = 'mainboard')}
						class="px-4 py-1.5 rounded-lg text-sm font-medium transition-colors
							{activeTab === 'mainboard' ? 'bg-amber-500 text-gray-950' : 'bg-gray-800 text-gray-400 hover:text-white'}">
						Mainboard ({totalMain})
					</button>
					<button onclick={() => (activeTab = 'sideboard')}
						class="px-4 py-1.5 rounded-lg text-sm font-medium transition-colors
							{activeTab === 'sideboard' ? 'bg-amber-500 text-gray-950' : 'bg-gray-800 text-gray-400 hover:text-white'}">
						Sideboard ({totalSide})
					</button>
					{#if maybeboard.length > 0 || activeTab === 'maybeboard'}
						<button onclick={() => (activeTab = 'maybeboard')}
							class="px-4 py-1.5 rounded-lg text-sm font-medium transition-colors
								{activeTab === 'maybeboard' ? 'bg-amber-500 text-gray-950' : 'bg-gray-800 text-gray-400 hover:text-white'}">
							Maybeboard ({totalMaybe})
						</button>
					{/if}
				</div>
				<div class="flex gap-1 bg-gray-800 rounded-lg p-1 shrink-0">
					<button onclick={() => (viewMode = 'list')}
						class="px-3 py-1 rounded text-sm transition-colors {viewMode === 'list' ? 'bg-gray-600 text-white' : 'text-gray-400 hover:text-white'}">
						☰ Liste
					</button>
					<button onclick={() => (viewMode = 'grid')}
						class="px-3 py-1 rounded text-sm transition-colors {viewMode === 'grid' ? 'bg-gray-600 text-white' : 'text-gray-400 hover:text-white'}">
						⊞ Grille
					</button>
				</div>
			</div>


			<!-- Action buttons -->
			<div class="flex gap-2 pt-1">
				<button
					onclick={() => { showSearch = !showSearch; showImport = false; }}
					class="flex-1 py-2.5 border border-dashed border-gray-700 hover:border-amber-600 text-gray-500 hover:text-amber-400 rounded-xl text-sm transition-colors"
				>{showSearch ? '↑ Masquer' : '+ Ajouter une carte'}</button>
				<button
					onclick={() => { showImport = !showImport; showSearch = false; }}
					class="flex-1 py-2.5 border border-dashed border-gray-700 hover:border-blue-600 text-gray-500 hover:text-blue-400 rounded-xl text-sm transition-colors"
				>{showImport ? '↑ Masquer' : '↑ Importer (MTGA/Moxfield)'}</button>
			</div>

			<!-- Search panel -->
			{#if showSearch}
				<div class="bg-gray-800 border border-gray-700 rounded-xl p-4 space-y-3">
					<!-- Category selector -->
					<div class="flex items-center gap-2 flex-wrap">
						<span class="text-xs text-gray-500">Ajouter en :</span>
						<button
							onclick={() => (addCategory = 'auto')}
							class="text-xs px-2.5 py-1 rounded-lg border transition-colors
								{addCategory === 'auto' ? 'bg-amber-600 border-amber-500 text-white' : 'border-gray-600 text-gray-400 hover:text-gray-200'}"
						>Auto (type)</button>
						{#each [['sideboard','Sideboard'],['commander','Commander'],['companion','Compagnon'],['maybeboard','Maybeboard'],['mainboard','Mainboard']] as [cat, label]}
							<button
								onclick={() => (addCategory = cat)}
								class="text-xs px-2.5 py-1 rounded-lg border transition-colors
									{addCategory === cat ? 'bg-amber-600 border-amber-500 text-white' : 'border-gray-600 text-gray-400 hover:text-gray-200'}"
							>{label}</button>
						{/each}
					</div>
					<!-- Search input + autocomplete -->
					<div class="relative flex gap-2">
						<div class="relative flex-1">
							<input
								bind:value={searchQuery}
								oninput={onSearchInput}
								onkeydown={onSearchKeydown}
								onfocus={() => searchQuery.length >= 2 && suggestions.length > 0 && (showSuggestions = true)}
								onblur={() => setTimeout(() => (showSuggestions = false), 150)}
								type="text"
								placeholder="Rechercher une carte..."
								class="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-amber-500 text-sm"
								autocomplete="off"
							/>
							{#if showSuggestions && suggestions.length > 0}
								<ul class="absolute z-50 top-full mt-1 left-0 right-0 bg-gray-800 border border-gray-700 rounded-xl shadow-2xl overflow-hidden">
									{#each suggestions as s, i}
										<li>
											<button onmousedown={() => pickSuggestion(s)}
												class="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-gray-700 transition-colors {i === highlightedIdx ? 'bg-gray-700' : ''}">
												<CardImage scryfallId={s.scryfallId} size="small" alt={s.name} class="w-8 h-11 rounded object-cover shrink-0" />
												<div class="flex-1 min-w-0">
													{#if s.foreignName}
														<span class="text-white text-sm font-medium">{s.foreignName}</span>
														<span class="text-gray-400 text-xs ml-1">({s.name})</span>
													{:else}
														<span class="text-white text-sm font-medium">{s.name}</span>
													{/if}
													<div class="flex items-center gap-2 mt-0.5">
														<span class="text-xs font-mono text-gray-500">{s.setCode}</span>
														{#if s.language}<span class="text-xs text-amber-500">{s.language}</span>{/if}
													</div>
												</div>
											</button>
										</li>
									{/each}
								</ul>
							{/if}
						</div>
						<button onclick={() => search()} disabled={searching}
							class="px-4 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-gray-950 font-semibold rounded-lg text-sm shrink-0">
							{searching ? '...' : 'Chercher'}
						</button>
					</div>
					<!-- Results -->
					{#if searchResults.length > 0}
						<div class="max-h-96 overflow-y-auto space-y-1">
							{#each searchResults as card (card.uuid)}
								<div class="flex items-center gap-3 px-3 py-2 hover:bg-gray-700 rounded-lg transition-colors">
									<CardImage scryfallId={card.scryfallId} size="small" alt={card.name} class="w-8 h-11 rounded object-cover shrink-0" />
									<div class="flex-1 min-w-0">
										<span class="text-sm text-white font-medium block truncate">
											{#if card.matchedForeignName}
												{card.matchedForeignName}
												<span class="text-gray-500 font-normal text-xs">({card.name})</span>
											{:else}
												{card.name}
											{/if}
										</span>
										<div class="flex items-center gap-2 mt-0.5">
											<span class="text-xs text-gray-500 font-mono">{card.setCode}</span>
											<RarityBadge rarity={card.rarity} />
										</div>
									</div>
									<ManaCost cost={card.manaCost} />
									<button onclick={() => addCard(card)}
										class="text-xs px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded-lg font-medium shrink-0">
										+ {addCategory === 'auto' ? typeCategory(card.type) : addCategory === 'commander' ? 'Cmd' : addCategory === 'sideboard' ? 'Side' : addCategory === 'companion' ? 'Comp' : addCategory === 'maybeboard' ? 'Maybe' : addCategory}
									</button>
								</div>
							{/each}
						</div>
					{/if}
				</div>
			{/if}

			<!-- Import panel -->
			{#if showImport}
				<div class="bg-gray-800 border border-gray-700 rounded-xl p-4 space-y-3">
					<p class="text-sm text-gray-400">Collez une liste MTGA ou Moxfield :</p>
					<textarea
						bind:value={importText}
						rows="8"
						placeholder="4 Lightning Bolt&#10;4 Lightning Bolt (M11) 149&#10;&#10;Commander&#10;1 Atraxa, Praetors' Voice&#10;&#10;Sideboard&#10;2 Pyroblast"
						class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-amber-500 text-sm font-mono resize-y"
					></textarea>
					<div class="flex items-center gap-3">
						<button onclick={doImport} disabled={importing || !importText.trim()}
							class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold rounded-lg text-sm">
							{importing ? 'Import...' : 'Importer'}
						</button>
						{#if importResult}
							<span class="text-sm text-green-400">{importResult.imported} carte(s) importée(s)</span>
							{#if importResult.skipped.length > 0}
								<span class="text-sm text-yellow-400">{importResult.skipped.length} ignorée(s)</span>
							{/if}
						{/if}
					</div>
					{#if importResult?.skipped.length}
						<div class="text-xs text-gray-500 space-y-0.5">
							<p class="font-medium text-gray-400">Lignes ignorées :</p>
							{#each importResult.skipped as line}<p class="font-mono">{line}</p>{/each}
						</div>
					{/if}
				</div>
			{/if}
			<!-- Grouping selector (list view only) -->
			{#if viewMode === 'list'}
				<div class="flex items-center gap-2 flex-wrap">
					<span class="text-xs text-gray-500">Grouper par :</span>
					{#each GROUP_OPTIONS as opt}
						<button
							onclick={() => (groupBy = opt.mode)}
							class="text-xs px-2.5 py-1 rounded-lg border transition-colors
								{groupBy === opt.mode ? 'bg-gray-600 border-gray-500 text-white' : 'border-gray-700 text-gray-500 hover:text-gray-300'}"
						>{opt.label}</button>
					{/each}
				</div>
			{/if}

			<!-- Empty state -->
			{#if activeEntries.length === 0}
				<div class="text-center py-8 text-gray-500 text-sm">
					Aucune carte. Utilisez la recherche pour en ajouter.
				</div>

			<!-- Grid view — grouped -->
			{:else if viewMode === 'grid'}
				<div class="space-y-5">
				{#each groupedEntries as group}
					<div class="space-y-2">
						<p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">
							{group.label} <span class="text-gray-600 normal-case font-normal">({group.count})</span>
						</p>
						<div class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3">
						{#each group.entries as entry (entry.id)}
							{@const scryfallId = cardCache[entry.card_uuid]?.identifiers?.scryfallId}
							{@const feas = feasMap.get(entry.card_uuid)}
							{@const isMissing = missingUuids.has(entry.card_uuid)}
							<div class="relative group cursor-pointer"
								onclick={() => (modalEntryId = entry.id)}
								role="button" tabindex="0"
								onkeydown={(e) => e.key === 'Enter' && (modalEntryId = entry.id)}
							>
								<CardImage {scryfallId} size="normal" alt={cardCache[entry.card_uuid]?.name ?? entry.card_uuid}
									class="w-full aspect-[488/680] object-cover rounded-lg {isMissing ? 'ring-2 ring-red-500' : ''}" />
								<span class="absolute bottom-1 left-1 bg-gray-900/90 text-white text-xs font-bold px-1.5 py-0.5 rounded">
									{entry.quantity}×
								</span>
								{#if isMissing}
									<span class="absolute top-1 right-1 bg-red-600/90 text-white text-xs font-bold px-1.5 py-0.5 rounded">
										{feas && feas.owned > 0 ? `${feas.owned}/${feas.needed}` : '✕'}
									</span>
								{/if}
								<div class="absolute inset-0 bg-black/60 rounded-lg opacity-0 group-hover:opacity-100 pointer-events-none group-hover:pointer-events-auto transition-opacity flex flex-col items-center justify-end pb-4 gap-1">
									<div class="flex gap-2" onclick={(e) => e.stopPropagation()} role="none">
										<button onclick={() => changeQty(entry.id, -1, entry.quantity)}
											class="w-7 h-7 rounded-full bg-gray-700 hover:bg-red-700 text-white font-bold">−</button>
										<button onclick={() => changeQty(entry.id, +1, entry.quantity)}
											class="w-7 h-7 rounded-full bg-gray-700 hover:bg-green-700 text-white font-bold">+</button>
									</div>
								</div>
							</div>
						{/each}
						</div>
					</div>
				{/each}
				</div>

			<!-- List view — grouped -->
			{:else}
				<div class="space-y-4">
					{#each groupedEntries as group}
						<div class="space-y-1">
							<p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">
								{group.label} <span class="text-gray-600 normal-case font-normal">({group.count})</span>
							</p>
							{#each group.entries as entry (entry.id)}
								{@const card = cardCache[entry.card_uuid]}
								{@const scryfallId = card?.identifiers?.scryfallId}
								<div
									class="flex items-center gap-2 px-3 py-2 bg-gray-800 rounded-xl border {missingUuids.has(entry.card_uuid) ? 'border-red-800' : 'border-gray-700'} hover:border-gray-500 transition-colors cursor-pointer group"
									onmouseenter={() => (hoveredCard = scryfallId ?? null)}
									onmouseleave={() => (hoveredCard = null)}
									onclick={() => (modalEntryId = entry.id)}
									role="button"
									tabindex="0"
									onkeydown={(e) => e.key === 'Enter' && (modalEntryId = entry.id)}
								>
									<!-- +/− (stop propagation to avoid opening modal) -->
									<div class="flex items-center gap-1 shrink-0" onclick={(e) => e.stopPropagation()} role="none">
										<button onclick={() => changeQty(entry.id, -1, entry.quantity)}
											class="w-6 h-6 flex items-center justify-center rounded bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm">−</button>
										<span class="text-sm font-semibold text-gray-300 w-5 text-center">{entry.quantity}</span>
										<button onclick={() => changeQty(entry.id, +1, entry.quantity)}
											class="w-6 h-6 flex items-center justify-center rounded bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm">+</button>
									</div>
									<span class="flex-1 text-sm text-white group-hover:text-amber-400 transition-colors font-medium min-w-0 truncate">
										{card?.name ?? entry.card_uuid}
									</span>
									{#if entry.category !== 'mainboard' && entry.category !== activeTab}
										<span class="text-xs text-blue-400 shrink-0">{entry.category}</span>
									{/if}
									{#if card}<ManaCost cost={card.manaCost} />{/if}
									{#if missingUuids.has(entry.card_uuid)}
										{@const feas = feasMap.get(entry.card_uuid)}
										<span class="text-xs text-red-400 shrink-0">
											{feas && feas.owned > 0 ? `${feas.owned}/${feas.needed}` : 'manquante'}
										</span>
									{/if}
									<button onclick={(e) => { e.stopPropagation(); removeCard(entry.id); }}
										class="text-gray-600 hover:text-red-400 transition-colors text-sm shrink-0 opacity-0 group-hover:opacity-100">✕</button>
								</div>
							{/each}
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Right: stats + feasibility -->
		<div class="space-y-5">
			<div class="bg-gray-800 border border-gray-700 rounded-xl p-4">
				<DeckStats entries={mainboard} {cardCache} />
			</div>

			{#if feasibility && feasibility.missing.length > 0}
				<div class="bg-red-900/20 border border-red-800 rounded-xl p-4 space-y-2">
					<p class="text-sm font-semibold text-red-400">Cartes à acquérir ({feasibility.missing.length})</p>
					{#each feasibility.missing as c}
						<div class="flex items-center gap-2 text-sm">
							<a href="/cards/{c.card_uuid}" class="text-white hover:text-amber-400 flex-1">{c.name}</a>
							<span class="text-red-400 text-xs">−{c.missing}</span>
						</div>
					{/each}
				</div>
			{:else if feasibility}
				<div class="bg-green-900/20 border border-green-800 rounded-xl p-4">
					<p class="text-sm text-green-400">Toutes les cartes sont dans votre collection !</p>
				</div>
			{/if}
		</div>
	</div>
</div>
{/if}

<!-- Hover preview -->
{#if hoveredCard && viewMode === 'list'}
	<div class="fixed bottom-6 right-6 z-50 pointer-events-none">
		<CardImage scryfallId={hoveredCard} size="normal" alt="preview"
			class="w-48 rounded-xl shadow-2xl border border-gray-600" />
	</div>
{/if}

<!-- Card detail modal -->
{#if modalEntry}
	<DeckCardModal
		entry={modalEntry}
		card={modalCard}
		{deckCategories}
		onclose={() => (modalEntryId = null)}
		onquantitychange={modalChangeQty}
		oncategorychange={modalChangeCategory}
		ondelete={modalDelete}
	/>
{/if}

<!-- Export modal -->
{#if showExport}
	<div class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
		<div class="bg-gray-800 border border-gray-700 rounded-xl p-6 w-full max-w-lg space-y-4">
			<div class="flex items-center justify-between">
				<h2 class="text-lg font-semibold text-white">Export MTGA / Moxfield</h2>
				<button onclick={() => (showExport = false)} class="text-gray-400 hover:text-white text-xl">✕</button>
			</div>
			<textarea
				readonly
				value={exportText}
				rows="14"
				class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-white text-sm font-mono resize-y focus:outline-none"
				onclick={(e) => (e.target as HTMLTextAreaElement).select()}
			></textarea>
			<p class="text-xs text-gray-500">Cliquez dans la zone pour tout sélectionner.</p>
		</div>
	</div>
{/if}

{#if toast}
	<div class="fixed bottom-6 right-6 bg-gray-700 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-medium z-40">
		{toast}
	</div>
{/if}
