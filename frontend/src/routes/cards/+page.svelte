<script lang="ts">
	import { searchCards, suggestCards, listSets } from '$lib/api';
	import type { CardSummary, SetSummary, CardSuggestion } from '$lib/api';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { untrack } from 'svelte';
	import ManaCost from '$lib/components/ManaCost.svelte';
	import RarityBadge from '$lib/components/RarityBadge.svelte';
	import CardImage from '$lib/components/CardImage.svelte';
	import AddToCollectionModal from '$lib/components/AddToCollectionModal.svelte';
	import { cardSearchSort as s } from '$lib/cardSearchSort.svelte';

	let query = $state('');
	let selectedSet = $state('');
	let selectedType = $state('');
	let results: CardSummary[] = $state([]);
	let sets: SetSummary[] = $state([]);
	let loading = $state(false);
	let searched = $state(false);
	let modalCard: CardSummary | null = $state(null);
	let toast = $state<string | null>(null);

	// Autocomplete
	let suggestions: CardSuggestion[] = $state([]);
	let showSuggestions = $state(false);
	let suggestTimeout: ReturnType<typeof setTimeout> | null = null;
	let highlightedIdx = $state(-1);

	// Advanced search
	let showAdvanced = $state(false);
	let selectedColors = $state<Set<string>>(new Set());
	let colorMatch = $state<'any' | 'all' | 'exact' | 'exclude'>('any');
	let textSearch = $state('');
	let selectedRarities = $state<Set<string>>(new Set());
	let cmcMin = $state<number | null>(null);
	let cmcMax = $state<number | null>(null);
	let selectedTypes = $state<Set<string>>(new Set());
	let subtypeSearch = $state('');
	let isLegendary = $state(false);
	let selectedFormat = $state('');

	const COLOR_ICONS: { key: string; label: string }[] = [
		{ key: 'W', label: 'Blanc'    },
		{ key: 'U', label: 'Bleu'     },
		{ key: 'B', label: 'Noir'     },
		{ key: 'R', label: 'Rouge'    },
		{ key: 'G', label: 'Vert'     },
		{ key: 'C', label: 'Incolore' },
	];
	const RARITIES = [
		{ key: 'common',   label: 'Commune'      },
		{ key: 'uncommon', label: 'Inhabituelle' },
		{ key: 'rare',     label: 'Rare'         },
		{ key: 'mythic',   label: 'Mythique'     },
	];
	const CARD_TYPES = [
		'Creature', 'Instant', 'Sorcery', 'Artifact',
		'Enchantment', 'Land', 'Planeswalker', 'Battle',
	];
	const TYPE_LABELS: Record<string, string> = {
		Creature: 'Créature', Instant: 'Éphémère', Sorcery: 'Rituel',
		Artifact: 'Artefact', Enchantment: 'Enchantement', Land: 'Terrain',
		Planeswalker: 'Planeswalker', Battle: 'Bataille',
	};
	const FORMATS = [
		{ key: 'standard',       label: 'Standard'         },
		{ key: 'pioneer',        label: 'Pioneer'          },
		{ key: 'modern',         label: 'Modern'           },
		{ key: 'legacy',         label: 'Legacy'           },
		{ key: 'vintage',        label: 'Vintage'          },
		{ key: 'commander',      label: 'Commander'        },
		{ key: 'pauper',         label: 'Pauper'           },
		{ key: 'historic',       label: 'Historic'         },
		{ key: 'timeless',       label: 'Timeless'         },
		{ key: 'brawl',          label: 'Brawl'            },
		{ key: 'oathbreaker',    label: 'Oathbreaker'      },
		{ key: 'paupercommander',label: 'Pauper Commander' },
		{ key: 'oldschool',      label: 'Old School'       },
		{ key: 'premodern',      label: 'Premodern'        },
	];

	function toggleColor(c: string) {
		const s = new Set(selectedColors);
		s.has(c) ? s.delete(c) : s.add(c);
		selectedColors = s;
	}

	function toggleRarity(r: string) {
		const s = new Set(selectedRarities);
		s.has(r) ? s.delete(r) : s.add(r);
		selectedRarities = s;
	}

	function toggleType(t: string) {
		const s = new Set(selectedTypes);
		s.has(t) ? s.delete(t) : s.add(t);
		selectedTypes = s;
	}

	const hasAdvancedFilters = $derived(
		selectedColors.size > 0 || selectedRarities.size > 0 ||
		textSearch.trim().length > 0 || cmcMin != null || cmcMax != null ||
		selectedTypes.size > 0 || subtypeSearch.trim().length > 0 ||
		isLegendary || selectedFormat !== ''
	);

	// Restore all filters from URL on every navigation (handles back button).
	// IMPORTANT: anyParam uses ONLY p.get() calls — never reads $state vars — to avoid
	// creating extra reactive dependencies that would re-trigger the effect on every keystroke.
	$effect(() => {
		const p = page.url.searchParams;
		query        = p.get('q')    ?? '';
		selectedSet  = p.get('set')  ?? '';
		selectedType = p.get('type') ?? '';
		const colors = p.get('colors') ?? '';
		selectedColors   = colors ? new Set(colors.split(',')) : new Set();
		colorMatch       = (p.get('color_match') ?? 'any') as typeof colorMatch;
		textSearch       = p.get('text')    ?? '';
		const rar        = p.get('rarity')  ?? '';
		selectedRarities = rar ? new Set(rar.split(',')) : new Set();
		cmcMin           = p.get('cmc_min') ? Number(p.get('cmc_min')) : null;
		cmcMax           = p.get('cmc_max') ? Number(p.get('cmc_max')) : null;
		const types      = p.get('types')   ?? '';
		selectedTypes    = types ? new Set(types.split(',')) : new Set();
		subtypeSearch    = p.get('subtype') ?? '';
		isLegendary      = p.get('legendary') === '1';
		selectedFormat   = p.get('format')  ?? '';

		// Only URL param values here — no $state reads
		const anyParam =
			p.get('q') || p.get('set') || p.get('type') || p.get('colors') ||
			p.get('rarity') || p.get('text') || p.get('cmc_min') || p.get('cmc_max') ||
			p.get('types') || p.get('subtype') || p.get('legendary') || p.get('format');
		if (anyParam) untrack(() => runSearch());
	});

	async function loadSets() {
		sets = await listSets();
		sets.sort((a, b) => (b.releaseDate ?? '').localeCompare(a.releaseDate ?? ''));
	}

	function buildUrl() {
		const p = new URLSearchParams();
		if (query)       p.set('q',           query);
		if (selectedSet) p.set('set',         selectedSet);
		if (selectedType)p.set('type',        selectedType);
		if (selectedColors.size)   p.set('colors',   [...selectedColors].join(','));
		if (colorMatch !== 'any')  p.set('color_match', colorMatch);
		if (textSearch.trim())     p.set('text',     textSearch.trim());
		if (selectedRarities.size) p.set('rarity',   [...selectedRarities].join(','));
		if (cmcMin != null)        p.set('cmc_min',  String(cmcMin));
		if (cmcMax != null)        p.set('cmc_max',  String(cmcMax));
		if (selectedTypes.size)    p.set('types',    [...selectedTypes].join(','));
		if (subtypeSearch.trim())  p.set('subtype',  subtypeSearch.trim());
		if (isLegendary)           p.set('legendary','1');
		if (selectedFormat)        p.set('format',   selectedFormat);
		return '/cards' + (p.toString() ? '?' + p.toString() : '');
	}

	async function runSearch() {
		showSuggestions = false;
		loading = true;
		searched = true;
		try {
			results = await searchCards({
				q: query, set: selectedSet, type: selectedType,
				colors: [...selectedColors].join(','),
				color_match: colorMatch,
				text: textSearch.trim() || undefined,
				rarity: [...selectedRarities].join(','),
				cmc_min: cmcMin ?? undefined,
				cmc_max: cmcMax ?? undefined,
				types: [...selectedTypes].join(',') || undefined,
				subtype: subtypeSearch.trim() || undefined,
				supertype: isLegendary ? 'Legendary' : undefined,
				format: selectedFormat || undefined,
				limit: 60,
			});
		} finally {
			loading = false;
		}
	}

	async function search(q = query) {
		query = q;
		await goto(buildUrl(), { replaceState: true, keepFocus: true, noScroll: true });
		// $effect handles runSearch after URL change
	}

	function onInput() {
		highlightedIdx = -1;
		if (suggestTimeout) clearTimeout(suggestTimeout);
		if (query.length < 2) {
			suggestions = [];
			showSuggestions = false;
			return;
		}
		suggestTimeout = setTimeout(async () => {
			suggestions = await suggestCards(query, 10);
			showSuggestions = suggestions.length > 0;
		}, 220);
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			if (highlightedIdx >= 0 && suggestions[highlightedIdx]) {
				pickSuggestion(suggestions[highlightedIdx]);
			} else {
				search();
			}
		} else if (e.key === 'ArrowDown') {
			e.preventDefault();
			highlightedIdx = Math.min(highlightedIdx + 1, suggestions.length - 1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			highlightedIdx = Math.max(highlightedIdx - 1, -1);
		} else if (e.key === 'Escape') {
			showSuggestions = false;
		}
	}

	function pickSuggestion(s: CardSuggestion) {
		query = s.foreignName ?? s.name;
		showSuggestions = false;
		// Clear filters so the suggestion's card is always found
		selectedSet = '';
		selectedType = '';
		selectedColors = new Set();
		selectedRarities = new Set();
		textSearch = '';
		cmcMin = null;
		cmcMax = null;
		selectedTypes = new Set();
		subtypeSearch = '';
		isLegendary = false;
		selectedFormat = '';
		search(query);
	}

	function onBlur() {
		setTimeout(() => (showSuggestions = false), 150);
	}

	const RARITY_ORDER: Record<string, number> = { common: 0, uncommon: 1, rare: 2, mythic: 3 };
	const COLOR_ORDER = 'WUBRG';

	const sortedResults = $derived.by(() => {
		if (s.sortKey === 'none') return results;
		return [...results].sort((a, b) => {
			let cmp = 0;
			if (s.sortKey === 'name') {
				cmp = (a.matchedForeignName ?? a.name).localeCompare(b.matchedForeignName ?? b.name);
			} else if (s.sortKey === 'cmc') {
				cmp = (a.manaValue ?? 0) - (b.manaValue ?? 0);
			} else if (s.sortKey === 'rarity') {
				cmp = (RARITY_ORDER[a.rarity] ?? 0) - (RARITY_ORDER[b.rarity] ?? 0);
			} else if (s.sortKey === 'color') {
				const ca = a.colors?.split(',')[0] ?? 'Z';
				const cb = b.colors?.split(',')[0] ?? 'Z';
				cmp = (COLOR_ORDER.indexOf(ca) + 1 || 99) - (COLOR_ORDER.indexOf(cb) + 1 || 99);
			} else if (s.sortKey === 'set') {
				cmp = a.setCode.localeCompare(b.setCode);
			} else if (s.sortKey === 'price') {
				cmp = (a.eur ?? -1) - (b.eur ?? -1);
			}
			return s.sortAsc ? cmp : -cmp;
		});
	});

	function setSort(key: typeof s.sortKey) {
		if (s.sortKey === key) s.sortAsc = !s.sortAsc;
		else { s.sortKey = key; s.sortAsc = true; }
	}

	function showToast(msg: string) {
		toast = msg;
		setTimeout(() => (toast = null), 2500);
	}

	loadSets();
</script>

<div class="space-y-6">
	<h1 class="text-2xl font-bold text-amber-400">Recherche de cartes</h1>

	<!-- Search bar -->
	<div class="space-y-3">
		<div class="flex flex-wrap gap-3">
			<!-- Input + suggestions -->
			<div class="relative flex-1 min-w-48">
				<input
					bind:value={query}
					oninput={onInput}
					onkeydown={onKeydown}
					onfocus={() => query.length >= 2 && suggestions.length > 0 && (showSuggestions = true)}
					onblur={onBlur}
					type="text"
					placeholder="Nom de la carte (français ou anglais)..."
					class="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-amber-500"
					autocomplete="off"
				/>

				{#if showSuggestions && suggestions.length > 0}
					<ul class="absolute z-50 top-full mt-1 left-0 right-0 bg-gray-800 border border-gray-700 rounded-xl shadow-2xl overflow-hidden">
						{#each suggestions as s, i}
							<li>
								<button
									onmousedown={() => pickSuggestion(s)}
									class="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-gray-700 transition-colors
										{i === highlightedIdx ? 'bg-gray-700' : ''}"
								>
									<CardImage
										scryfallId={s.scryfallId}
										size="small"
										alt={s.name}
										class="w-8 h-11 rounded object-cover shrink-0"
									/>
									<div class="flex-1 min-w-0">
										{#if s.foreignName}
											<span class="text-white font-medium">{s.foreignName}</span>
											<span class="text-gray-400 text-xs ml-1">({s.name})</span>
										{:else}
											<span class="text-white font-medium">{s.name}</span>
										{/if}
										<div class="flex items-center gap-2 mt-0.5">
											<span class="text-xs font-mono text-gray-500">{s.setCode}</span>
											{#if s.language}
												<span class="text-xs text-amber-500">{s.language}</span>
											{/if}
										</div>
									</div>
								</button>
							</li>
						{/each}
					</ul>
				{/if}
			</div>

			<select
				bind:value={selectedSet}
				onchange={() => search()}
				class="px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-amber-500"
			>
				<option value="">Tous les sets</option>
				{#each sets as s}
					<option value={s.code}>{s.name} ({s.code})</option>
				{/each}
			</select>

			<input
				bind:value={selectedType}
				type="text"
				placeholder="Type (ex: Creature)"
				class="w-44 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-amber-500"
			/>

			<button
				onclick={() => search()}
				disabled={loading}
				class="px-6 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-gray-950 font-semibold rounded-lg transition-colors"
			>
				{loading ? 'Recherche...' : 'Rechercher'}
			</button>
		</div>

		<!-- Advanced search toggle -->
		<button
			onclick={() => (showAdvanced = !showAdvanced)}
			class="text-sm text-gray-500 hover:text-amber-400 transition-colors flex items-center gap-1"
		>
			{showAdvanced ? '▲' : '▼'} Recherche avancée
			{#if hasAdvancedFilters}<span class="text-amber-400 text-xs font-medium ml-1">(filtres actifs)</span>{/if}
		</button>

		{#if showAdvanced}
			<div class="bg-gray-800 border border-gray-700 rounded-xl p-4 space-y-4">

				<!-- Colors -->
				<div class="space-y-2">
					<span class="text-xs text-gray-500 uppercase tracking-wide">Couleurs</span>
					<div class="flex flex-wrap items-center gap-3">
						<div class="flex gap-1.5">
							{#each COLOR_ICONS as c}
								<button
									onclick={() => toggleColor(c.key)}
									title={c.label}
									class="w-8 h-8 rounded-full border-2 flex items-center justify-center transition-all
										{selectedColors.has(c.key) ? 'border-amber-400 scale-110' : 'border-gray-600 opacity-60 hover:opacity-100'}"
								>
									<img
										src="https://svgs.scryfall.io/card-symbols/{c.key}.svg"
										alt={c.label}
										class="w-5 h-5"
									/>
								</button>
							{/each}
						</div>
						{#if selectedColors.size > 0}
							<div class="flex gap-2 text-xs flex-wrap">
								{#each [['any','Contient'], ['all','Contient tous'], ['exact','Exactement'], ['exclude','Exclut']] as [val, label]}
									<label class="flex items-center gap-1 cursor-pointer">
										<input
											type="radio"
											name="color_match"
											value={val}
											bind:group={colorMatch}
											class="accent-amber-500"
										/>
										<span class="text-gray-300">{label}</span>
									</label>
								{/each}
							</div>
						{/if}
					</div>
				</div>

				<!-- Rarity -->
				<div class="space-y-2">
					<span class="text-xs text-gray-500 uppercase tracking-wide">Rareté</span>
					<div class="flex flex-wrap gap-2">
						{#each RARITIES as r}
							<button
								onclick={() => toggleRarity(r.key)}
								class="text-xs px-3 py-1 rounded-full border transition-colors
									{selectedRarities.has(r.key)
										? r.key === 'mythic' ? 'bg-orange-500/20 border-orange-500 text-orange-300'
										: r.key === 'rare' ? 'bg-yellow-500/20 border-yellow-500 text-yellow-300'
										: r.key === 'uncommon' ? 'bg-gray-400/20 border-gray-400 text-gray-200'
										: 'bg-gray-600/20 border-gray-500 text-gray-300'
										: 'border-gray-700 text-gray-500 hover:border-gray-500 hover:text-gray-300'}"
							>{r.label}</button>
						{/each}
					</div>
				</div>

				<!-- Text + CMC -->
				<div class="flex flex-wrap gap-4">
					<div class="flex-1 min-w-48 space-y-1">
						<label for="adv-text" class="text-xs text-gray-500 uppercase tracking-wide">Texte de règles</label>
						<input
							id="adv-text"
							bind:value={textSearch}
							type="text"
							placeholder="ex: flying, draw a card..."
							class="w-full px-3 py-1.5 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm placeholder-gray-500 focus:outline-none focus:border-amber-500"
						/>
					</div>
					<div class="space-y-1">
						<label for="adv-cmc-min" class="text-xs text-gray-500 uppercase tracking-wide">CMC</label>
						<div class="flex items-center gap-2">
							<input
								id="adv-cmc-min"
								bind:value={cmcMin}
								type="number"
								min="0"
								placeholder="Min"
								class="w-16 px-2 py-1.5 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm text-center focus:outline-none focus:border-amber-500"
							/>
							<span class="text-gray-500 text-sm">–</span>
							<input
								bind:value={cmcMax}
								type="number"
								min="0"
								placeholder="Max"
								class="w-16 px-2 py-1.5 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm text-center focus:outline-none focus:border-amber-500"
							/>
						</div>
					</div>
				</div>

				<!-- Types -->
				<div class="space-y-2">
					<span class="text-xs text-gray-500 uppercase tracking-wide">Type de carte</span>
					<div class="flex flex-wrap gap-1.5">
						{#each CARD_TYPES as t}
							<button
								onclick={() => toggleType(t)}
								class="text-xs px-3 py-1 rounded-full border transition-colors
									{selectedTypes.has(t)
										? 'bg-blue-600/20 border-blue-500 text-blue-300'
										: 'border-gray-700 text-gray-500 hover:border-gray-500 hover:text-gray-300'}"
							>{TYPE_LABELS[t] ?? t}</button>
						{/each}
					</div>
				</div>

				<!-- Legendary toggle -->
				<button
					onclick={() => (isLegendary = !isLegendary)}
					class="text-xs px-3 py-1 rounded-full border transition-colors w-fit
						{isLegendary
							? 'bg-amber-500/20 border-amber-500 text-amber-300'
							: 'border-gray-700 text-gray-500 hover:border-gray-500 hover:text-gray-300'}"
				>⚔ Légendaire</button>

				<!-- Subtype -->
				<div class="space-y-1">
					<label for="adv-subtype" class="text-xs text-gray-500 uppercase tracking-wide">Sous-type</label>
					<input
						id="adv-subtype"
						bind:value={subtypeSearch}
						type="text"
						placeholder="ex: Zombie, Dragon, Wizard, Merfolk…"
						class="w-full px-3 py-1.5 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm placeholder-gray-500 focus:outline-none focus:border-amber-500"
					/>
				</div>

				<!-- Format -->
				<div class="space-y-2">
					<label for="adv-format" class="text-xs text-gray-500 uppercase tracking-wide">Format légal dans</label>
					<select
						id="adv-format"
						bind:value={selectedFormat}
						class="px-3 py-1.5 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:border-amber-500"
					>
						<option value="">Tous les formats</option>
						{#each FORMATS as f}
							<option value={f.key}>{f.label}</option>
						{/each}
					</select>
				</div>

				<div class="flex gap-2 pt-1">
					<button
						onclick={() => search()}
						disabled={loading}
						class="px-5 py-1.5 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-gray-950 font-semibold rounded-lg text-sm transition-colors"
					>
						Appliquer les filtres
					</button>
					{#if hasAdvancedFilters}
						<button
							onclick={() => {
								selectedColors = new Set();
								selectedRarities = new Set();
								textSearch = '';
								cmcMin = null;
								cmcMax = null;
								selectedTypes = new Set();
								subtypeSearch = '';
								isLegendary = false;
								selectedFormat = '';
								search();
							}}
							class="px-4 py-1.5 text-sm text-gray-400 hover:text-red-400 border border-gray-700 hover:border-red-700 rounded-lg transition-colors"
						>
							Effacer les filtres
						</button>
					{/if}
				</div>
			</div>
		{/if}
	</div>

	<!-- Results -->
	{#if loading}
		<div class="text-center py-12 text-gray-400">Chargement...</div>
	{:else if searched && results.length === 0}
		<div class="text-center py-12 text-gray-400">Aucune carte trouvée.</div>
	{:else if results.length > 0}
		<div class="flex flex-wrap items-center gap-2">
			<p class="text-sm text-gray-500 mr-2">{results.length} carte(s) trouvée(s)</p>
			{#each [['none','Défaut'],['name','Nom'],['cmc','CMC'],['rarity','Rareté'],['color','Couleur'],['set','Set'],['price','Prix €']] as [key, label]}
				<button onclick={() => setSort(key as any)}
					class="text-xs px-2.5 py-1 rounded-full border transition-colors
						{s.sortKey === key ? 'bg-amber-900/40 border-amber-500 text-amber-300' : 'bg-gray-800 border-gray-600 text-gray-500 hover:border-gray-500'}">
					{label}{s.sortKey === key && key !== 'none' ? (s.sortAsc ? ' ↑' : ' ↓') : ''}
				</button>
			{/each}
		</div>
		<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
			{#each sortedResults as card (card.uuid)}
				<div class="group relative flex flex-col bg-gray-800 border border-gray-700 rounded-xl overflow-hidden hover:border-amber-500 transition-colors">
					<!-- Card image -->
					<a href="/cards/{card.uuid}" class="block">
						<CardImage
							scryfallId={card.scryfallId}
							size="normal"
							alt={card.name}
							class="w-full aspect-[488/680] object-cover"
						/>
					</a>

					<!-- Footer -->
					<div class="p-2 space-y-1">
						<div class="flex items-start justify-between gap-1">
							<a
								href="/cards/{card.uuid}"
								class="text-xs font-semibold text-white hover:text-amber-400 transition-colors leading-tight line-clamp-2"
							>
								{#if card.matchedForeignName}
									{card.matchedForeignName}
									<span class="text-gray-500 font-normal">({card.name})</span>
								{:else}
									{card.name}
								{/if}
							</a>
							<ManaCost cost={card.manaCost} />
						</div>

						<div class="flex items-center gap-1 flex-wrap">
							<span class="text-[10px] text-gray-500 font-mono">{card.setCode}</span>
							<RarityBadge rarity={card.rarity} />
							{#if card.matchedLanguage}
								<span class="text-[10px] text-amber-500">{card.matchedLanguage}</span>
							{/if}
						</div>

						<button
							onclick={() => (modalCard = card)}
							class="w-full text-xs py-1 rounded-lg font-medium bg-gray-700 hover:bg-amber-600 hover:text-white text-gray-300 transition-colors"
						>
							+ Collection
						</button>
					</div>
				</div>
			{/each}
		</div>
	{:else}
		<div class="text-center py-16 text-gray-500">
			Tapez un nom (français ou anglais) pour explorer les cartes.
		</div>
	{/if}
</div>

{#if modalCard}
	<AddToCollectionModal
		card={modalCard}
		onclose={() => (modalCard = null)}
		onadded={() => {
			showToast(`${modalCard!.name} ajoutée à la collection !`);
			modalCard = null;
		}}
	/>
{/if}

{#if toast}
	<div class="fixed bottom-6 right-6 bg-green-700 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-medium">
		{toast}
	</div>
{/if}
