<script lang="ts">
	const BASE = '/api';

	interface Stats {
		total_cards: number;
		unique_cards: number;
		foil_count: number;
		color_distribution: Record<string, number>;
		rarity_distribution: Record<string, number>;
		total_decks: number;
		decks: { id: string; name: string; format: string; description: string; card_count: number }[];
		set_completion: { code: string; name: string; owned: number; total: number; pct: number }[];
		collection_eur: number;
		collection_usd: number;
		prices_loaded: boolean;
		prices_file_age_days: number | null;
		data_file_age_days: number | null;
	}

	import { toast } from '$lib/toast.svelte';

	let stats = $state<Stats | null>(null);
	let loading = $state(true);
	let refreshing = $state(false);
	let refreshingData = $state(false);

	let initializing = $state(false);

	async function load() {
		const res = await fetch(`${BASE}/stats/`);
		if (res.status === 503) {
			// Données MTGjson pas encore chargées — réessayer dans 3s
			initializing = true;
			setTimeout(load, 3000);
			return;
		}
		initializing = false;
		if (res.ok) stats = await res.json();
		loading = false;
	}

	async function refreshPrices() {
		refreshing = true;
		toast.loading('Téléchargement des prix…');
		try {
			const res = await fetch(`${BASE}/stats/refresh-prices`, { method: 'POST' });
			const data = await res.json();
			if (data.success) {
				toast.success(`Prix mis à jour — ${data.card_count?.toLocaleString('fr-FR')} cartes`);
				await load();
			} else {
				toast.error(data.reason === 'no_internet' ? 'Pas de connexion internet' : 'Échec du téléchargement');
			}
		} catch {
			toast.error('Erreur réseau');
		} finally {
			refreshing = false;
		}
	}

	async function refreshData() {
		refreshingData = true;
		toast.loading('Mise à jour des données cartes…');
		try {
			const res = await fetch(`${BASE}/stats/refresh-data`, { method: 'POST' });
			const data = await res.json();
			if (data.success) {
				toast.success('Données mises à jour — nouvelles extensions disponibles');
				await load();
			} else {
				toast.error(data.reason === 'no_internet' ? 'Pas de connexion internet' : 'Échec de la mise à jour');
			}
		} catch {
			toast.error('Erreur réseau');
		} finally {
			refreshingData = false;
		}
	}

	load();

	const COLOR_META: Record<string, { label: string; bg: string; text: string; symbol: string }> = {
		W: { label: 'Blanc',  bg: 'bg-yellow-100', text: 'text-yellow-900', symbol: 'W' },
		U: { label: 'Bleu',   bg: 'bg-blue-700',   text: 'text-blue-100',   symbol: 'U' },
		B: { label: 'Noir',   bg: 'bg-gray-900',    text: 'text-gray-200',   symbol: 'B' },
		R: { label: 'Rouge',  bg: 'bg-red-700',     text: 'text-red-100',    symbol: 'R' },
		G: { label: 'Vert',   bg: 'bg-green-700',   text: 'text-green-100',  symbol: 'G' },
	};

	const RARITY_META: Record<string, { label: string; color: string }> = {
		mythic:   { label: 'Mythique',    color: 'text-orange-400' },
		rare:     { label: 'Rare',        color: 'text-yellow-400' },
		uncommon: { label: 'Inhabituelle',color: 'text-gray-300'   },
		common:   { label: 'Commune',     color: 'text-gray-500'   },
	};

	const colorMax = $derived(
		stats ? Math.max(1, ...Object.values(stats.color_distribution)) : 1
	);
	const rarityMax = $derived(
		stats ? Math.max(1, ...Object.values(stats.rarity_distribution)) : 1
	);
</script>

<div class="space-y-8">

	<!-- Header -->
	<div class="flex items-center justify-between flex-wrap gap-4">
		<div>
			<h1 class="text-3xl font-bold text-amber-400">Dashboard</h1>
			<p class="text-sm text-gray-500 mt-1">Vue d'ensemble de ta collection et de tes decks</p>
		</div>
		<div class="flex gap-3">
			<a href="/cards" class="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-gray-950 font-semibold rounded-lg text-sm transition-colors">
				Parcourir les cartes
			</a>
			<a href="/collection" class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg text-sm transition-colors">
				Ma collection
			</a>
			<a href="/decks" class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg text-sm transition-colors">
				Mes decks
			</a>
		</div>
	</div>

	{#if initializing}
		<div class="text-center py-16 space-y-3">
			<div class="flex items-center justify-center gap-3 text-amber-400">
				<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
				</svg>
				<span class="font-medium">Téléchargement des données MTGjson en cours…</span>
			</div>
			<p class="text-sm text-gray-500">Première utilisation : environ 5-10 minutes (~600 MB)</p>
		</div>
	{:else if loading}
		<div class="text-center py-16 text-gray-400">Chargement...</div>
	{:else if stats}

		<!-- Stats cards -->
		<div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
			<div class="bg-gray-800 border border-gray-700 rounded-xl p-4 text-center">
				<p class="text-3xl font-bold text-white">{stats.total_cards.toLocaleString('fr-FR')}</p>
				<p class="text-xs text-gray-500 mt-1 uppercase tracking-wide">Cartes totales</p>
			</div>
			<div class="bg-gray-800 border border-gray-700 rounded-xl p-4 text-center">
				<p class="text-3xl font-bold text-white">{stats.unique_cards.toLocaleString('fr-FR')}</p>
				<p class="text-xs text-gray-500 mt-1 uppercase tracking-wide">Cartes uniques</p>
			</div>
			<div class="bg-gray-800 border border-gray-700 rounded-xl p-4 text-center">
				<p class="text-3xl font-bold text-purple-400">{stats.foil_count.toLocaleString('fr-FR')}</p>
				<p class="text-xs text-gray-500 mt-1 uppercase tracking-wide">Foils</p>
			</div>
			<div class="bg-gray-800 border border-gray-700 rounded-xl p-4 text-center">
				<p class="text-3xl font-bold text-amber-400">{stats.total_decks}</p>
				<p class="text-xs text-gray-500 mt-1 uppercase tracking-wide">Decks</p>
			</div>
			{#if stats.prices_loaded}
				<div class="bg-gray-800 border border-gray-700 rounded-xl p-4 text-center">
					<p class="text-2xl font-bold text-green-400">€{stats.collection_eur.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
					<p class="text-xs text-gray-500 mt-1 uppercase tracking-wide">Valeur EUR</p>
				</div>
				<div class="bg-gray-800 border border-gray-700 rounded-xl p-4 text-center">
					<p class="text-2xl font-bold text-green-400">${stats.collection_usd.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
					<p class="text-xs text-gray-500 mt-1 uppercase tracking-wide">Valeur USD</p>
				</div>
			{:else}
				<div class="col-span-2 bg-gray-800 border border-dashed border-gray-600 rounded-xl p-4 flex flex-col items-center justify-center gap-2 text-center">
					<p class="text-xs text-gray-500">Prix non chargés</p>
					<button
						onclick={refreshPrices}
						disabled={refreshing}
						class="text-xs px-3 py-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
					>{refreshing ? 'Téléchargement…' : '↓ Télécharger les prix'}</button>
				</div>
			{/if}
		</div>

		<!-- Refresh feedback + manual refresh buttons -->
		<div class="flex items-center gap-3 flex-wrap">
			{#if stats.prices_loaded}
				<p class="text-xs text-gray-600">
					Prix {stats.prices_file_age_days != null ? `mis à jour il y a ${Math.round(stats.prices_file_age_days)} j` : ''}
				</p>
				<button
					onclick={refreshPrices}
					disabled={refreshing}
					class="text-xs px-3 py-1 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-gray-300 rounded-lg transition-colors"
				>{refreshing ? 'Téléchargement…' : '↻ Rafraîchir les prix'}</button>
			{/if}
			<p class="text-xs text-gray-600">
				Données {stats.data_file_age_days != null ? `mises à jour il y a ${Math.round(stats.data_file_age_days)} j` : ''}
			</p>
			<button
				onclick={refreshData}
				disabled={refreshingData}
				class="text-xs px-3 py-1 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-gray-300 rounded-lg transition-colors"
				title="Re-télécharge AllPrintings.sqlite depuis MTGjson (nouvelles extensions)"
			>{refreshingData ? 'Téléchargement…' : '↻ Mettre à jour les données'}</button>
		</div>

		<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

			<!-- Color distribution -->
			<div class="bg-gray-800 border border-gray-700 rounded-xl p-5 space-y-3">
				<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide">Répartition couleurs</h2>
				<div class="space-y-2">
					{#each Object.entries(COLOR_META) as [key, meta]}
						{@const count = stats.color_distribution[key] ?? 0}
						{@const pct = Math.round((count / colorMax) * 100)}
						<div class="flex items-center gap-3">
							<span class="w-16 text-xs text-gray-400 shrink-0">{meta.label}</span>
							<div class="flex-1 bg-gray-700 rounded-full h-3 overflow-hidden">
								<div
									class="h-full rounded-full transition-all {key === 'W' ? 'bg-yellow-200' : key === 'U' ? 'bg-blue-500' : key === 'B' ? 'bg-gray-500' : key === 'R' ? 'bg-red-500' : 'bg-green-500'}"
									style="width: {pct}%"
								></div>
							</div>
							<span class="text-xs text-gray-500 w-10 text-right shrink-0">{count}</span>
						</div>
					{/each}
				</div>
			</div>

			<!-- Rarity distribution -->
			<div class="bg-gray-800 border border-gray-700 rounded-xl p-5 space-y-3">
				<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide">Répartition raretés</h2>
				<div class="space-y-2">
					{#each Object.entries(RARITY_META) as [key, meta]}
						{@const count = stats.rarity_distribution[key] ?? 0}
						{@const pct = Math.round((count / rarityMax) * 100)}
						<div class="flex items-center gap-3">
							<span class="w-24 text-xs {meta.color} shrink-0">{meta.label}</span>
							<div class="flex-1 bg-gray-700 rounded-full h-3 overflow-hidden">
								<div
									class="h-full rounded-full transition-all {key === 'mythic' ? 'bg-orange-400' : key === 'rare' ? 'bg-yellow-400' : key === 'uncommon' ? 'bg-gray-300' : 'bg-gray-500'}"
									style="width: {pct}%"
								></div>
							</div>
							<span class="text-xs text-gray-500 w-10 text-right shrink-0">{count}</span>
						</div>
					{/each}
				</div>
			</div>
		</div>

		<!-- Set completion -->
		{#if stats.set_completion.length > 0}
			<div class="bg-gray-800 border border-gray-700 rounded-xl p-5 space-y-3">
				<div class="flex items-center justify-between">
					<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide">Progression par set</h2>
					<a href="/collection" class="text-xs text-amber-500 hover:text-amber-400">Analyser les manques →</a>
				</div>
				<div class="space-y-1.5 max-h-72 overflow-y-auto pr-1">
					{#each stats.set_completion as s}
						<div class="flex items-center gap-3">
							<span class="text-xs font-mono text-gray-500 w-10 shrink-0">{s.code}</span>
							<span class="text-xs text-gray-300 w-40 truncate shrink-0">{s.name}</span>
							<div class="flex-1 bg-gray-700 rounded-full h-2 overflow-hidden">
								<div
									class="h-full rounded-full {s.pct >= 100 ? 'bg-green-500' : s.pct >= 75 ? 'bg-amber-400' : s.pct >= 25 ? 'bg-blue-500' : 'bg-gray-500'}"
									style="width: {Math.min(s.pct, 100)}%"
								></div>
							</div>
							<span class="text-xs text-gray-500 w-20 text-right shrink-0">{s.owned}/{s.total} ({s.pct}%)</span>
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Decks -->
		{#if stats.decks.length > 0}
			<div class="space-y-3">
				<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide">Mes decks</h2>
				<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
					{#each stats.decks as deck}
						<a href="/decks/{deck.id}"
							class="bg-gray-800 border border-gray-700 hover:border-amber-600 rounded-xl p-4 transition-colors group block">
							<div class="flex items-start justify-between gap-2">
								<div class="min-w-0">
									<p class="font-semibold text-white group-hover:text-amber-400 transition-colors truncate">{deck.name}</p>
									{#if deck.format}
										<p class="text-xs text-amber-500 mt-0.5">{deck.format}</p>
									{/if}
									{#if deck.description}
										<p class="text-xs text-gray-500 mt-1 truncate">{deck.description}</p>
									{/if}
								</div>
								<span class="text-xs text-gray-500 shrink-0 mt-1">{deck.card_count} cartes</span>
							</div>
						</a>
					{/each}
					<a href="/decks"
						class="bg-gray-800 border border-dashed border-gray-700 hover:border-amber-600 rounded-xl p-4 transition-colors flex items-center justify-center text-gray-500 hover:text-amber-400 text-sm">
						+ Nouveau deck
					</a>
				</div>
			</div>
		{:else}
			<div class="bg-gray-800 border border-dashed border-gray-700 rounded-xl p-8 text-center space-y-3">
				<p class="text-gray-500">Aucun deck pour l'instant.</p>
				<a href="/decks" class="inline-block px-4 py-2 bg-amber-500 hover:bg-amber-400 text-gray-950 font-semibold rounded-lg text-sm transition-colors">
					Créer un deck
				</a>
			</div>
		{/if}

	{/if}
</div>
