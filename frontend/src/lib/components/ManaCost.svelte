<script lang="ts">
	let { cost }: { cost: string | null | undefined } = $props();

	// Parse "{W}{2}{G/W}{T}" into individual symbol strings
	const symbols = $derived(
		cost ? [...cost.matchAll(/\{([^}]+)\}/g)].map((m) => m[1]) : []
	);

	// Map MTGjson symbol notation to Scryfall SVG filenames
	// e.g. "G/W" → "GW", "2/W" → "2W", "W/P" → "WP"
	function toSvgName(symbol: string): string {
		return symbol.replace(/\//g, '').toUpperCase();
	}

	function svgUrl(symbol: string): string {
		return `https://svgs.scryfall.io/card-symbols/${toSvgName(symbol)}.svg`;
	}
</script>

{#if symbols.length > 0}
	<span class="inline-flex gap-0.5 flex-wrap items-center">
		{#each symbols as s}
			<img
				src={svgUrl(s)}
				alt={`{${s}}`}
				title={`{${s}}`}
				class="inline-block w-4 h-4"
				loading="lazy"
			/>
		{/each}
	</span>
{/if}
