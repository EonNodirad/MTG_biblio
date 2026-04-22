<script lang="ts">
	import {
		getCollection, getCard, updateCollectionEntry,
		removeFromCollection, getMissingCards
	} from '$lib/api';
	import type { CollectionEntry, CardDetail } from '$lib/api';
	import RarityBadge from '$lib/components/RarityBadge.svelte';
	import ManaCost from '$lib/components/ManaCost.svelte';
	import CardImage from '$lib/components/CardImage.svelte';
	import { collectionFilters as f } from '$lib/collectionFilters.svelte';

	type EnrichedEntry = CollectionEntry & { card?: CardDetail };

	// ── État local (ne survit pas à la navigation — c'est intentionnel) ──────
	let entries        = $state<EnrichedEntry[]>([]);
	let loading        = $state(true);
	let toast          = $state<string | null>(null);
	let missingSetCode = $state('');
	let missingResult  = $state<any>(null);
	let loadingMissing = $state(false);

	// ── Constantes UI ─────────────────────────────────────────────────────────
	const conditions = ['NM', 'LP', 'MP', 'HP', 'DMG'];
	const conditionColors: Record<string, string> = {
		NM: 'bg-green-700 text-green-100 border-green-600',
		LP: 'bg-lime-700 text-lime-100 border-lime-600',
		MP: 'bg-yellow-700 text-yellow-100 border-yellow-600',
		HP: 'bg-orange-700 text-orange-100 border-orange-600',
		DMG: 'bg-red-800 text-red-100 border-red-700',
	};
	const conditionInactive = 'bg-gray-700 text-gray-500 border-gray-600 hover:bg-gray-600';
	const RARITY_ORDER: Record<string, number> = { common: 0, uncommon: 1, rare: 2, mythic: 3 };
	const COLOR_ORDER = 'WUBRG';
	const COLOR_NAMES: Record<string, string> = { W:'Blanc', U:'Bleu', B:'Noir', R:'Rouge', G:'Vert', C:'Incolore' };
	const TYPE_LIST = ['Creature', 'Instant', 'Sorcery', 'Enchantment', 'Artifact', 'Planeswalker', 'Land', 'Battle'];
	const TYPE_LABELS: Record<string, string> = {
		Creature: 'Créature', Instant: 'Éphémère', Sorcery: 'Rituel',
		Enchantment: 'Enchantement', Artifact: 'Artefact',
		Planeswalker: 'Planeswalker', Land: 'Terrain', Battle: 'Bataille',
	};
	const FORMATS = [
		{ key: 'standard', label: 'Standard' }, { key: 'pioneer', label: 'Pioneer' },
		{ key: 'modern', label: 'Modern' },     { key: 'legacy', label: 'Legacy' },
		{ key: 'vintage', label: 'Vintage' },   { key: 'commander', label: 'Commander' },
		{ key: 'pauper', label: 'Pauper' },     { key: 'historic', label: 'Historic' },
		{ key: 'timeless', label: 'Timeless' }, { key: 'brawl', label: 'Brawl' },
		{ key: 'oathbreaker', label: 'Oathbreaker' }, { key: 'paupercommander', label: 'Pauper Cmdr' },
		{ key: 'oldschool', label: 'Old School' }, { key: 'premodern', label: 'Premodern' },
	];

	// ── Chargement ───────────────────────────────────────────────────────────
	async function load() {
		loading = true;
		const raw = await getCollection();
		entries = await Promise.all(
			raw.map(async (e) => {
				try { return { ...e, card: await getCard(e.card_uuid) }; }
				catch { return { ...e }; }
			})
		);
		loading = false;
	}

	// ── Filtres + tri (tout via le store persistant `f`) ──────────────────────
	const displayed = $derived.by(() => {
		let list = [...entries];

		if (f.search) {
			const q = f.search.toLowerCase();
			list = list.filter(e => e.card?.name?.toLowerCase().includes(q));
		}

		if (f.filterColors.size > 0) {
			list = list.filter(e => {
				const cols = e.card?.colors ?? [];
				const wantsColorless = f.filterColors.has('C');
				const colorList = [...f.filterColors].filter(c => c !== 'C');
				if (f.colorMatch === 'any') {
					if (wantsColorless && cols.length === 0) return true;
					return colorList.some(c => cols.includes(c));
				} else if (f.colorMatch === 'all') {
					return colorList.every(c => cols.includes(c));
				} else if (f.colorMatch === 'exact') {
					const sorted = [...colorList].sort((a, b) => COLOR_ORDER.indexOf(a) - COLOR_ORDER.indexOf(b));
					const cardSorted = [...cols].sort((a, b) => COLOR_ORDER.indexOf(a) - COLOR_ORDER.indexOf(b));
					return sorted.join('') === cardSorted.join('') && (!wantsColorless || cols.length === 0);
				} else if (f.colorMatch === 'exclude') {
					if (wantsColorless && cols.length > 0) return false;
					return colorList.every(c => !cols.includes(c));
				}
				return true;
			});
		}

		if (f.filterRarities.size > 0) {
			list = list.filter(e => f.filterRarities.has(e.card?.rarity ?? ''));
		}

		if (f.filterTypes.size > 0) {
			list = list.filter(e => [...f.filterTypes].some(t => e.card?.type?.includes(t)));
		}

		if (f.filterText.trim()) {
			const q = f.filterText.trim().toLowerCase();
			list = list.filter(e => e.card?.text?.toLowerCase().includes(q));
		}

		if (f.filterSubtype.trim()) {
			const q = f.filterSubtype.trim().toLowerCase();
			list = list.filter(e => e.card?.subtypes?.some(s => s.toLowerCase().includes(q)));
		}

		if (f.filterLegendary) {
			list = list.filter(e => e.card?.supertypes?.includes('Legendary'));
		}

		if (f.cmcMin != null) list = list.filter(e => (e.card?.manaValue ?? 0) >= f.cmcMin!);
		if (f.cmcMax != null) list = list.filter(e => (e.card?.manaValue ?? 0) <= f.cmcMax!);

		if (f.filterFormat) {
			list = list.filter(e => e.card?.legalities?.[f.filterFormat] === 'Legal');
		}

		list.sort((a, b) => {
			let cmp = 0;
			if (f.sortKey === 'name') {
				cmp = (a.card?.name ?? '').localeCompare(b.card?.name ?? '');
			} else if (f.sortKey === 'cmc') {
				cmp = (a.card?.manaValue ?? 0) - (b.card?.manaValue ?? 0);
			} else if (f.sortKey === 'rarity') {
				cmp = (RARITY_ORDER[a.card?.rarity ?? ''] ?? 0) - (RARITY_ORDER[b.card?.rarity ?? ''] ?? 0);
			} else if (f.sortKey === 'color') {
				const ca = a.card?.colors?.[0] ?? 'Z';
				const cb = b.card?.colors?.[0] ?? 'Z';
				cmp = (COLOR_ORDER.indexOf(ca) + 1 || 99) - (COLOR_ORDER.indexOf(cb) + 1 || 99);
			} else if (f.sortKey === 'set') {
				cmp = (a.card?.setCode ?? '').localeCompare(b.card?.setCode ?? '');
			} else if (f.sortKey === 'price') {
				const getPrice = (e: EnrichedEntry) => {
					const p = e.card?.prices as { eur?: number | null; eur_foil?: number | null } | null;
					if (!p) return 0;
					return (e.foil ? (p.eur_foil ?? p.eur) : p.eur) ?? 0;
				};
				cmp = getPrice(a) - getPrice(b);
			}
			return f.sortAsc ? cmp : -cmp;
		});

		return list;
	});

	function toggleColor(c: string) {
		const s = new Set(f.filterColors);
		s.has(c) ? s.delete(c) : s.add(c);
		f.filterColors = s;
	}
	function toggleRarity(r: string) {
		const s = new Set(f.filterRarities);
		s.has(r) ? s.delete(r) : s.add(r);
		f.filterRarities = s;
	}
	function toggleType(t: string) {
		const s = new Set(f.filterTypes);
		s.has(t) ? s.delete(t) : s.add(t);
		f.filterTypes = s;
	}
	function setSort(key: typeof f.sortKey) {
		if (f.sortKey === key) f.sortAsc = !f.sortAsc;
		else { f.sortKey = key; f.sortAsc = true; }
	}
	function clearFilters() {
		f.search = ''; f.filterColors = new Set(); f.colorMatch = 'any';
		f.filterRarities = new Set(); f.filterTypes = new Set();
		f.filterText = ''; f.filterSubtype = ''; f.filterLegendary = false;
		f.filterFormat = ''; f.cmcMin = null; f.cmcMax = null;
	}

	const hasFilters = $derived(
		!!f.search || f.filterColors.size > 0 || f.filterRarities.size > 0 ||
		f.filterTypes.size > 0 || !!f.filterText.trim() || !!f.filterSubtype.trim() ||
		f.filterLegendary || !!f.filterFormat || f.cmcMin != null || f.cmcMax != null
	);
	const hasAdvancedFilters = $derived(
		!!f.filterText.trim() || !!f.filterSubtype.trim() || f.filterLegendary ||
		!!f.filterFormat || f.cmcMin != null || f.cmcMax != null
	);

	// ── Actions ───────────────────────────────────────────────────────────────
	async function changeQty(entry: EnrichedEntry, delta: number) {
		const newQty = Math.max(0, entry.quantity + delta);
		if (newQty === 0) {
			await removeFromCollection(entry.id);
			entries = entries.filter(e => e.id !== entry.id);
		} else {
			await updateCollectionEntry(entry.id, { quantity: newQty });
			entries = entries.map(e => e.id === entry.id ? { ...e, quantity: newQty } : e);
		}
	}
	async function toggleFoil(entry: EnrichedEntry) {
		await updateCollectionEntry(entry.id, { foil: !entry.foil });
		entries = entries.map(e => e.id === entry.id ? { ...e, foil: !e.foil } : e);
	}
	async function changeCondition(entry: EnrichedEntry, condition: string) {
		await updateCollectionEntry(entry.id, { condition });
		entries = entries.map(e => e.id === entry.id ? { ...e, condition } : e);
	}
	async function remove(entry: EnrichedEntry) {
		await removeFromCollection(entry.id);
		entries = entries.filter(e => e.id !== entry.id);
		showToast('Carte supprimée.');
	}
	async function searchMissing() {
		if (!missingSetCode.trim()) return;
		loadingMissing = true;
		try { missingResult = await getMissingCards(missingSetCode.trim().toUpperCase()); }
		catch (e: any) { missingResult = { error: e.message }; }
		finally { loadingMissing = false; }
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
			method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: text,
		});
		const result = await res.json();
		showToast(`${result.imported} carte(s) importée(s)${result.skipped.length ? `, ${result.skipped.length} ignorée(s)` : ''}`);
		await load();
		(e.target as HTMLInputElement).value = '';
	}

	load();
</script>

<div class="space-y-6">

	<!-- Header -->
	<div class="flex items-center justify-between flex-wrap gap-3">
		<div>
			<h1 class="text-2xl font-bold text-amber-400">Ma collection</h1>
			<span class="text-sm text-gray-400">{displayed.length} / {entries.length} carte(s)</span>
		</div>
		<div class="flex gap-2 flex-wrap items-center">
			<div class="flex rounded-lg overflow-hidden border border-gray-700">
				<button onclick={() => (f.viewMode = 'list')}
					class="px-3 py-1.5 text-sm transition-colors {f.viewMode === 'list' ? 'bg-amber-500 text-gray-950 font-semibold' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}">
					Liste
				</button>
				<button onclick={() => (f.viewMode = 'grid')}
					class="px-3 py-1.5 text-sm transition-colors {f.viewMode === 'grid' ? 'bg-amber-500 text-gray-950 font-semibold' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}">
					Grille
				</button>
			</div>
			<a href="/api/collection/export/csv" download="collection.csv"
				class="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg transition-colors">
				↓ CSV
			</a>
			<label class="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg transition-colors cursor-pointer">
				↑ CSV <input type="file" accept=".csv" class="hidden" onchange={importCsv} />
			</label>
		</div>
	</div>

	<!-- Filtres -->
	<div class="bg-gray-800 border border-gray-700 rounded-xl p-4 space-y-3">
		<div class="flex gap-3 items-center">
			<input bind:value={f.search} type="text" placeholder="Rechercher par nom..."
				class="flex-1 px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500 text-sm focus:outline-none focus:border-amber-500" />
			{#if hasFilters}
				<button onclick={clearFilters} class="text-xs text-gray-400 hover:text-white transition-colors whitespace-nowrap">
					Effacer tout
				</button>
			{/if}
		</div>

		<!-- Couleurs -->
		<div class="flex flex-wrap gap-1.5 items-center">
			<span class="text-xs text-gray-500 w-16 shrink-0">Couleur</span>
			{#each ['W','U','B','R','G','C'] as c}
				<button onclick={() => toggleColor(c)}
					class="w-7 h-7 rounded-full flex items-center justify-center transition-all ring-2
						{f.filterColors.has(c) ? 'ring-amber-400 scale-110' : 'ring-transparent opacity-60 hover:opacity-90'}">
					<img src="https://svgs.scryfall.io/card-symbols/{c}.svg" alt={COLOR_NAMES[c]} class="w-6 h-6" />
				</button>
			{/each}
			{#if f.filterColors.size > 0}
				<div class="flex gap-2 text-xs flex-wrap ml-2">
					{#each [['any','Contient'], ['all','Contient tous'], ['exact','Exactement'], ['exclude','Exclut']] as [val, label]}
						<label class="flex items-center gap-1 cursor-pointer">
							<input type="radio" name="col_match" value={val} bind:group={f.colorMatch} class="accent-amber-500" />
							<span class="text-gray-300">{label}</span>
						</label>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Raretés -->
		<div class="flex flex-wrap gap-1.5 items-center">
			<span class="text-xs text-gray-500 w-16 shrink-0">Rareté</span>
			{#each ['common','uncommon','rare','mythic'] as r}
				<button onclick={() => toggleRarity(r)}
					class="text-xs px-2.5 py-1 rounded-full border transition-colors
						{f.filterRarities.has(r)
							? r === 'mythic' ? 'bg-orange-900/50 border-orange-500 text-orange-300'
							: r === 'rare'   ? 'bg-yellow-900/50 border-yellow-500 text-yellow-300'
							: r === 'uncommon' ? 'bg-gray-600 border-gray-400 text-gray-200'
							: 'bg-gray-700 border-gray-500 text-gray-300'
							: 'bg-gray-800 border-gray-600 text-gray-500 hover:border-gray-500'}">
					{r === 'common' ? 'Commune' : r === 'uncommon' ? 'Inhabituelle' : r === 'rare' ? 'Rare' : 'Mythique'}
				</button>
			{/each}
		</div>

		<!-- Types -->
		<div class="flex flex-wrap gap-1.5 items-center">
			<span class="text-xs text-gray-500 w-16 shrink-0">Type</span>
			{#each TYPE_LIST as t}
				<button onclick={() => toggleType(t)}
					class="text-xs px-2.5 py-1 rounded-full border transition-colors
						{f.filterTypes.has(t) ? 'bg-blue-900/50 border-blue-500 text-blue-300' : 'bg-gray-800 border-gray-600 text-gray-500 hover:border-gray-500'}">
					{TYPE_LABELS[t]}
				</button>
			{/each}
		</div>

		<!-- Avancé toggle -->
		<button
			onclick={() => (f.showAdvanced = !f.showAdvanced)}
			class="text-xs text-gray-500 hover:text-amber-400 transition-colors flex items-center gap-1">
			{f.showAdvanced ? '▲' : '▼'} Filtres avancés
			{#if hasAdvancedFilters}<span class="text-amber-400 font-medium ml-1">(actifs)</span>{/if}
		</button>

		{#if f.showAdvanced}
			<div class="space-y-3 border-t border-gray-700 pt-3">
				<div class="flex flex-wrap gap-4">
					<div class="flex-1 min-w-48 space-y-1">
						<label for="col-text" class="text-xs text-gray-500 uppercase tracking-wide">Texte de règles</label>
						<input id="col-text" bind:value={f.filterText} type="text" placeholder="ex: flying, draw a card..."
							class="w-full px-3 py-1.5 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm placeholder-gray-500 focus:outline-none focus:border-amber-500" />
					</div>
					<div class="space-y-1">
						<label for="col-cmc-min" class="text-xs text-gray-500 uppercase tracking-wide">CMC</label>
						<div class="flex items-center gap-2">
							<input id="col-cmc-min" bind:value={f.cmcMin} type="number" min="0" placeholder="Min"
								class="w-16 px-2 py-1.5 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm text-center focus:outline-none focus:border-amber-500" />
							<span class="text-gray-500 text-sm">–</span>
							<input bind:value={f.cmcMax} type="number" min="0" placeholder="Max"
								class="w-16 px-2 py-1.5 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm text-center focus:outline-none focus:border-amber-500" />
						</div>
					</div>
				</div>

				<div class="flex flex-wrap gap-4 items-end">
					<div class="flex-1 min-w-48 space-y-1">
						<label for="col-subtype" class="text-xs text-gray-500 uppercase tracking-wide">Sous-type</label>
						<input id="col-subtype" bind:value={f.filterSubtype} type="text" placeholder="ex: Zombie, Dragon, Wizard…"
							class="w-full px-3 py-1.5 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm placeholder-gray-500 focus:outline-none focus:border-amber-500" />
					</div>
					<button
						onclick={() => (f.filterLegendary = !f.filterLegendary)}
						class="text-xs px-3 py-1.5 rounded-full border transition-colors
							{f.filterLegendary ? 'bg-amber-500/20 border-amber-500 text-amber-300' : 'border-gray-600 text-gray-500 hover:border-gray-400 hover:text-gray-300'}">
						⚔ Légendaire
					</button>
				</div>

				<div class="space-y-1">
					<label for="col-format" class="text-xs text-gray-500 uppercase tracking-wide">Format légal dans</label>
					<select id="col-format" bind:value={f.filterFormat}
						class="px-3 py-1.5 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:border-amber-500">
						<option value="">Tous les formats</option>
						{#each FORMATS as fmt}
							<option value={fmt.key}>{fmt.label}</option>
						{/each}
					</select>
				</div>
			</div>
		{/if}

		<!-- Tri -->
		<div class="flex flex-wrap gap-1.5 items-center border-t border-gray-700 pt-3">
			<span class="text-xs text-gray-500 w-16 shrink-0">Trier</span>
			{#each [['name','Nom'],['cmc','CMC'],['rarity','Rareté'],['color','Couleur'],['set','Set'],['price','Prix €']] as [key, label]}
				<button onclick={() => setSort(key as any)}
					class="text-xs px-2.5 py-1 rounded-full border transition-colors
						{f.sortKey === key ? 'bg-amber-900/40 border-amber-500 text-amber-300' : 'bg-gray-800 border-gray-600 text-gray-500 hover:border-gray-500'}">
					{label} {f.sortKey === key ? (f.sortAsc ? '↑' : '↓') : ''}
				</button>
			{/each}
		</div>
	</div>

	{#if loading}
		<div class="text-center py-16 text-gray-400">Chargement...</div>
	{:else if entries.length === 0}
		<div class="text-center py-16 text-gray-500">
			Collection vide. <a href="/cards" class="text-amber-400 hover:underline">Parcourir les cartes</a>
		</div>
	{:else if displayed.length === 0}
		<div class="text-center py-10 text-gray-500 text-sm">Aucune carte ne correspond aux filtres.</div>
	{:else if f.viewMode === 'grid'}

		<!-- ── Vue GRILLE ─────────────────────────────────────────────────── -->
		<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
			{#each displayed as entry (entry.id)}
				{@const sid = entry.card?.identifiers?.scryfallId ?? null}
				<div class="group relative bg-gray-800 rounded-xl overflow-hidden border border-gray-700 hover:border-amber-600 transition-colors">
					<a href="/cards/{entry.card_uuid}">
						<CardImage scryfallId={sid} alt={entry.card?.name ?? ''} size="normal"
							class="w-full rounded-t-xl" />
					</a>
					<div class="absolute top-2 right-2 bg-gray-950/80 backdrop-blur text-white text-xs font-bold px-2 py-0.5 rounded-full">
						×{entry.quantity}
					</div>
					{#if entry.foil}
						<div class="absolute top-2 left-2 bg-purple-800/80 text-purple-200 text-xs px-1.5 py-0.5 rounded-full">Foil</div>
					{/if}
					<div class="p-2 space-y-1">
						<p class="text-xs font-semibold text-white truncate">{entry.card?.name ?? '—'}</p>
						<div class="flex items-center justify-between gap-1">
							<RarityBadge rarity={entry.card?.rarity ?? ''} />
							<ManaCost cost={entry.card?.manaCost} />
						</div>
						<div class="flex items-center justify-between pt-1">
							<button onclick={() => changeQty(entry, -1)}
								class="w-6 h-6 rounded-full bg-gray-700 hover:bg-red-900 text-white text-sm font-bold flex items-center justify-center transition-colors">−</button>
							<span class="text-xs text-gray-300 font-semibold">{entry.quantity}</span>
							<button onclick={() => changeQty(entry, +1)}
								class="w-6 h-6 rounded-full bg-gray-700 hover:bg-green-900 text-white text-sm font-bold flex items-center justify-center transition-colors">+</button>
						</div>
					</div>
				</div>
			{/each}
		</div>

	{:else}

		<!-- ── Vue LISTE ──────────────────────────────────────────────────── -->
		<div class="space-y-2">
			{#each displayed as entry (entry.id)}
				<div class="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 flex flex-wrap items-center gap-3">
					{#if entry.card?.identifiers?.scryfallId}
						<a href="/cards/{entry.card_uuid}" class="shrink-0">
							<CardImage scryfallId={entry.card.identifiers.scryfallId} size="art_crop"
								alt={entry.card.name} class="w-14 h-10 rounded object-cover" />
						</a>
					{/if}
					<div class="flex-1 min-w-40">
						<a href="/cards/{entry.card_uuid}"
							class="font-semibold text-white hover:text-amber-400 transition-colors">
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
					<button onclick={() => toggleFoil(entry)}
						class="text-xs px-2 py-1 rounded transition-colors
							{entry.foil ? 'bg-purple-800 text-purple-200' : 'bg-gray-700 text-gray-400 hover:bg-gray-600'}">
						Foil
					</button>
					<div class="flex gap-1">
						{#each conditions as c}
							<button onclick={() => changeCondition(entry, c)}
								class="text-xs px-2 py-1 rounded border font-medium transition-colors
									{entry.condition === c ? conditionColors[c] : conditionInactive}">{c}</button>
						{/each}
					</div>
					<div class="flex items-center gap-2">
						<button onclick={() => changeQty(entry, -1)}
							class="w-7 h-7 rounded-full bg-gray-700 hover:bg-gray-600 text-white font-bold flex items-center justify-center">−</button>
						<span class="w-6 text-center font-semibold text-white">{entry.quantity}</span>
						<button onclick={() => changeQty(entry, +1)}
							class="w-7 h-7 rounded-full bg-gray-700 hover:bg-gray-600 text-white font-bold flex items-center justify-center">+</button>
					</div>
					<button onclick={() => remove(entry)}
						class="text-gray-500 hover:text-red-400 transition-colors text-sm" title="Supprimer">✕</button>
				</div>
			{/each}
		</div>

	{/if}

	<!-- Cartes manquantes -->
	<div class="border-t border-gray-800 pt-6 space-y-4">
		<h2 class="text-lg font-semibold text-gray-300">Cartes manquantes par set</h2>
		<div class="flex gap-3">
			<input bind:value={missingSetCode} type="text" placeholder="Code du set (ex: MH2)"
				class="w-48 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-amber-500 uppercase" />
			<button onclick={searchMissing} disabled={loadingMissing}
				class="px-5 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-gray-950 font-semibold rounded-lg transition-colors">
				{loadingMissing ? '...' : 'Analyser'}
			</button>
		</div>
		{#if missingResult?.error}
			<p class="text-red-400 text-sm">{missingResult.error}</p>
		{:else if missingResult}
			<div class="bg-gray-800 border border-gray-700 rounded-xl p-4 space-y-3">
				<div class="flex gap-6 text-sm flex-wrap">
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
