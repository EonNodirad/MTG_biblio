<script lang="ts">
	let { text }: { text: string } = $props();

	function toSvgName(sym: string): string {
		return sym.replace(/\//g, '').toUpperCase();
	}

	function toHtml(t: string): string {
		return t.replace(/\{([^}]+)\}/g, (_, sym) => {
			const name = toSvgName(sym);
			const escaped = sym.replace(/"/g, '&quot;');
			return `<img src="https://svgs.scryfall.io/card-symbols/${name}.svg" alt="{${escaped}}" title="{${escaped}}" class="inline h-4 w-4 align-middle" loading="lazy" onerror="this.replaceWith(document.createTextNode('{${escaped}}'))">`;
		});
	}
</script>

<span class="leading-relaxed whitespace-pre-line">{@html toHtml(text)}</span>
