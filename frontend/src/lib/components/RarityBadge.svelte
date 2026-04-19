<script lang="ts">
	let { rarity }: { rarity: string } = $props();

	const classes: Record<string, string> = {
		common: 'bg-gray-100 text-gray-700',
		uncommon: 'bg-slate-200 text-slate-700',
		rare: 'bg-yellow-100 text-yellow-800',
		mythic: 'bg-orange-100 text-orange-800',
		special: 'bg-purple-100 text-purple-800',
		bonus: 'bg-pink-100 text-pink-800'
	};

	const cls = $derived(classes[rarity?.toLowerCase()] ?? 'bg-gray-100 text-gray-600');
</script>

<span class="inline-block px-2 py-0.5 rounded text-xs font-semibold capitalize {cls}">
	{rarity ?? '—'}
</span>
