<script lang="ts">
	import { getPrintings, updateCollectionEntry } from '$lib/api';
	import type { CardPrinting, CollectionEntry, CardDetail } from '$lib/api';

	type EnrichedEntry = CollectionEntry & { card?: CardDetail };

	let { entry, onchange, onclose }: {
		entry: EnrichedEntry;
		onchange: (updated: EnrichedEntry) => void;
		onclose: () => void;
	} = $props();

	let printings = $state<CardPrinting[]>([]);
	let loading   = $state(true);
	let saving    = $state<string | null>(null); // uuid en cours de sauvegarde

	$effect(() => {
		const name = entry.card?.name;
		if (!name) { loading = false; return; }
		getPrintings(name).then(p => { printings = p; loading = false; });
	});

	async function pick(printing: CardPrinting) {
		if (printing.uuid === entry.card_uuid) { onclose(); return; }
		saving = printing.uuid;
		try {
			await updateCollectionEntry(entry.id, { card_uuid: printing.uuid });
			onchange({ ...entry, card_uuid: printing.uuid, card: entry.card ? { ...entry.card, setCode: printing.setCode, identifiers: { scryfallId: printing.scryfallId ?? undefined } } : undefined });
		} finally {
			saving = null;
			onclose();
		}
	}

	const RARITY_COLOR: Record<string, string> = {
		mythic:   'text-orange-400',
		rare:     'text-yellow-400',
		uncommon: 'text-gray-300',
		common:   'text-gray-500',
	};
</script>

<!-- Backdrop -->
<div
	class="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
	onclick={onclose}
	onkeydown={(e) => e.key === 'Escape' && onclose()}
	role="button"
	tabindex="-1"
	aria-label="Fermer"
></div>

<!-- Panel -->
<div class="fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl flex flex-col max-h-[80vh]">
	<div class="flex items-center justify-between px-5 py-4 border-b border-gray-700 shrink-0">
		<div>
			<h2 class="font-semibold text-white">{entry.card?.name ?? 'Édition'}</h2>
			<p class="text-xs text-gray-400 mt-0.5">Choisir une édition</p>
		</div>
		<button onclick={onclose} class="text-gray-500 hover:text-white transition-colors text-lg">✕</button>
	</div>

	<div class="overflow-y-auto flex-1 p-2">
		{#if loading}
			<div class="text-center py-8 text-gray-400 text-sm">Chargement…</div>
		{:else if printings.length === 0}
			<div class="text-center py-8 text-gray-500 text-sm">Aucune édition trouvée.</div>
		{:else}
			{#each printings as p (p.uuid)}
				{@const isCurrent = p.uuid === entry.card_uuid}
				<button
					onclick={() => pick(p)}
					disabled={!!saving}
					class="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors text-left
						{isCurrent ? 'bg-amber-500/15 border border-amber-500/40' : 'hover:bg-gray-800 border border-transparent'}
						disabled:opacity-60"
				>
					<!-- Art thumbnail -->
					<div class="w-12 h-16 rounded-lg overflow-hidden shrink-0 bg-gray-800 border border-gray-700">
						{#if p.scryfallId}
							<img
								src="https://cards.scryfall.io/small/front/{p.scryfallId.slice(0,1)}/{p.scryfallId.slice(1,2)}/{p.scryfallId}.jpg"
								alt={p.setCode}
								class="w-full h-full object-cover"
								loading="lazy"
							/>
						{:else}
							<div class="w-full h-full flex items-center justify-center text-gray-600 text-xs">{p.setCode}</div>
						{/if}
					</div>
					<!-- Info -->
					<div class="flex-1 min-w-0">
						<div class="flex items-center gap-2">
							<span class="font-mono text-xs font-bold text-gray-200 uppercase">{p.setCode}</span>
							{#if isCurrent}
								<span class="text-[10px] bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded-full">actuelle</span>
							{/if}
						</div>
						<p class="text-xs text-gray-400 truncate mt-0.5">{p.setName ?? p.setCode}</p>
						<div class="flex items-center gap-2 mt-1">
							<span class="text-[10px] {RARITY_COLOR[p.rarity] ?? 'text-gray-500'} capitalize">{p.rarity}</span>
							{#if p.releaseDate}
								<span class="text-[10px] text-gray-600">{p.releaseDate.slice(0, 4)}</span>
							{/if}
						</div>
					</div>
					{#if saving === p.uuid}
						<div class="w-4 h-4 border-2 border-amber-400 border-t-transparent rounded-full animate-spin shrink-0"></div>
					{/if}
				</button>
			{/each}
		{/if}
	</div>
</div>
