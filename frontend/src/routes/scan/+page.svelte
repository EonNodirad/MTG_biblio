<script lang="ts">
	import { addToCollection } from '$lib/api';
	import CardImage from '$lib/components/CardImage.svelte';
	import ManaCost from '$lib/components/ManaCost.svelte';

	type ScanResult = {
		uuid: string;
		scryfall_id: string;
		distance: number;
		confidence: 'high' | 'medium' | 'low' | 'none';
		quad: [number, number][];    // contour détecté (peut être vide)
		guide: [number, number, number, number]; // [x1,y1,x2,y2] normalisé 0-1
		name: string | null;
		set_code: string | null;
		type: string | null;
		mana_cost: string | null;
		rarity: string | null;
	};

	let videoEl    = $state<HTMLVideoElement | null>(null);
	let captureCanvas = $state<HTMLCanvasElement | null>(null);  // caché, pour capturer
	let overlayCanvas = $state<HTMLCanvasElement | null>(null);  // visible, pour dessiner

	let mode       = $state<'idle' | 'camera' | 'upload'>('idle');
	let streaming  = $state(false);
	let scanning   = $state(false);
	let result     = $state<ScanResult | null>(null);
	let error      = $state<string | null>(null);
	let toast      = $state<string | null>(null);
	let adding     = $state(false);
	let scanCount    = $state(0);
	let intervalId   = $state<ReturnType<typeof setInterval> | null>(null);
	let animFrameId  = $state<number | null>(null);
	let uuidHistory  = $state<string[]>([]);
	const STABLE_FRAMES = 2;   // 2 frames stables suffisent

	const cameraAvailable = $derived(
		typeof navigator !== 'undefined' &&
		!!navigator.mediaDevices?.getUserMedia &&
		(location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')
	);

	const CONF_COLOR: Record<string, string> = {
		high:   '#22c55e',
		medium: '#f59e0b',
		low:    '#ef4444',
		none:   '#6b7280',
	};
	const CONF_LABEL: Record<string, string> = {
		high:   'Confiance élevée',
		medium: 'Confiance moyenne',
		low:    'Confiance faible',
		none:   'Aucune correspondance',
	};

	// Synchronise les dimensions pixel du canvas avec l'affichage réel de la vidéo
	function syncOverlaySize() {
		if (!videoEl || !overlayCanvas) return;
		const w = videoEl.offsetWidth;
		const h = videoEl.offsetHeight;
		if (w > 0 && h > 0 && (overlayCanvas.width !== w || overlayCanvas.height !== h)) {
			overlayCanvas.width  = w;
			overlayCanvas.height = h;
		}
	}

	// Boucle de dessin — tourne à chaque frame via rAF
	function drawOverlay() {
		if (!overlayCanvas) { animFrameId = requestAnimationFrame(drawOverlay); return; }
		syncOverlaySize();

		const W   = overlayCanvas.width;
		const H   = overlayCanvas.height;
		const ctx = overlayCanvas.getContext('2d')!;
		ctx.clearRect(0, 0, W, H);

		// --- Cadre guide (toujours visible) ---
		// Utilise les coordonnées du backend si disponibles, sinon calcule localement
		let gx1: number, gy1: number, gx2: number, gy2: number;
		if (result?.guide?.length === 4) {
			[gx1, gy1, gx2, gy2] = result.guide.map((v, i) => v * (i % 2 === 0 ? W : H));
		} else {
			const gh = H * 0.60;
			const gw = gh * 0.716;
			gx1 = (W - gw) / 2; gy1 = (H - gh) / 2;
			gx2 = gx1 + gw;     gy2 = gy1 + gh;
		}

		const guideColor = result && result.confidence !== 'none'
			? CONF_COLOR[result.confidence]
			: 'rgba(255,255,255,0.5)';
		const gw = gx2 - gx1, gh = gy2 - gy1;
		const cs = 18; // longueur des coins

		// Rectangle guide en pointillés
		ctx.setLineDash([6, 4]);
		ctx.strokeStyle = guideColor;
		ctx.lineWidth   = 1.5;
		ctx.strokeRect(gx1, gy1, gw, gh);
		ctx.setLineDash([]);

		// Coins en trait plein
		ctx.strokeStyle = guideColor;
		ctx.lineWidth   = 3;
		for (const [cx, cy, dx, dy] of [
			[gx1, gy1,  1,  1], [gx2, gy1, -1,  1],
			[gx2, gy2, -1, -1], [gx1, gy2,  1, -1],
		] as [number, number, number, number][]) {
			ctx.beginPath();
			ctx.moveTo(cx + dx * cs, cy); ctx.lineTo(cx, cy); ctx.lineTo(cx, cy + dy * cs);
			ctx.stroke();
		}

		// --- Contour détecté (si disponible) ---
		if (result?.quad?.length === 4) {
			const pts = result.quad.map(([x, y]) => [x * W, y * H] as [number, number]);
			ctx.beginPath();
			ctx.moveTo(pts[0][0], pts[0][1]);
			for (let i = 1; i < 4; i++) ctx.lineTo(pts[i][0], pts[i][1]);
			ctx.closePath();
			ctx.strokeStyle = CONF_COLOR[result.confidence];
			ctx.lineWidth   = 2;
			ctx.stroke();
		}

		animFrameId = requestAnimationFrame(drawOverlay);
	}

	async function startCamera() {
		error = null;
		mode = 'camera';
		try {
			const stream = await navigator.mediaDevices.getUserMedia({
				video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } }
			});
			if (!videoEl) return;
			videoEl.srcObject = stream;
			await videoEl.play();
			streaming = true;
			await new Promise(r => setTimeout(r, 100));
			syncOverlaySize();
			animFrameId = requestAnimationFrame(drawOverlay);
			startScanning();
		} catch (e: any) {
			mode = 'idle';
			if (e?.name === 'NotAllowedError') {
				error = "Permission caméra refusée. Autorise l'accès dans les réglages du navigateur.";
			} else if (e?.name === 'NotFoundError') {
				error = "Aucune caméra trouvée sur cet appareil.";
			} else if (e?.name === 'NotReadableError') {
				error = "La caméra est déjà utilisée par une autre application.";
			} else if (!cameraAvailable) {
				error = "La caméra nécessite HTTPS ou localhost. Utilise le mode upload à la place.";
			} else {
				error = `Erreur caméra : ${e?.message ?? e}`;
			}
		}
	}

	async function scanUploadedFile(file: File) {
		error = null;
		result = null;
		mode = 'upload';
		scanning = true;
		try {
			const form = new FormData();
			form.append('file', file, file.name);
			const res = await fetch('/api/scan/', { method: 'POST', body: form });
			if (res.ok) {
				const data: ScanResult = await res.json();
				result = data;
				scanCount++;
			} else {
				error = `Erreur serveur : ${res.status}`;
			}
		} catch (e: any) {
			error = `Erreur : ${e?.message ?? e}`;
		} finally {
			scanning = false;
		}
	}

	function onFileInput(e: Event) {
		const file = (e.target as HTMLInputElement).files?.[0];
		if (file) scanUploadedFile(file);
	}

	function stopCamera() {
		if (intervalId)   { clearInterval(intervalId);         intervalId = null; }
		if (animFrameId)  { cancelAnimationFrame(animFrameId); animFrameId = null; }
		if (videoEl?.srcObject) {
			(videoEl.srcObject as MediaStream).getTracks().forEach(t => t.stop());
			videoEl.srcObject = null;
		}
		streaming = false;
		scanning  = false;
		result    = null;
		if (overlayCanvas) {
			const ctx = overlayCanvas.getContext('2d')!;
			ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
		}
	}

	function startScanning() {
		if (intervalId) clearInterval(intervalId);
		intervalId = setInterval(captureAndScan, 350);
	}

	async function captureAndScan() {
		if (!videoEl || !captureCanvas || videoEl.readyState < 2 || scanning) return;
		const ctx = captureCanvas.getContext('2d')!;
		// Envoie 640×360 max — pHash n'a pas besoin de plus
		const scale = Math.min(1, 640 / videoEl.videoWidth);
		captureCanvas.width  = Math.round(videoEl.videoWidth  * scale);
		captureCanvas.height = Math.round(videoEl.videoHeight * scale);
		ctx.drawImage(videoEl, 0, 0, captureCanvas.width, captureCanvas.height);

		scanning = true;
		captureCanvas.toBlob(async (blob) => {
			if (!blob) { scanning = false; return; }
			const form = new FormData();
			form.append('file', blob, 'frame.jpg');
			try {
				const res = await fetch('/api/scan/', { method: 'POST', body: form });
				if (res.ok) {
					const data: ScanResult = await res.json();
					scanCount++;

					if (data.confidence !== 'none') {
						uuidHistory = [...uuidHistory.slice(-(STABLE_FRAMES - 1)), data.uuid];
						// Valide seulement si le même UUID est stable
						if (uuidHistory.length >= STABLE_FRAMES && uuidHistory.every(u => u === data.uuid)) {
							result = data;
						}
						// Met quand même à jour le guide/quad pour l'overlay
						else if (result === null) result = { ...data, confidence: 'none' };
					} else {
						uuidHistory = [];
						result = data;  // pour afficher le cadre guide
					}
				}
			} catch { /* réseau */ }
			finally { scanning = false; }
		}, 'image/jpeg', 0.85);
	}

	async function addCard() {
		if (!result || result.confidence === 'none') return;
		adding = true;
		try {
			await addToCollection({ card_uuid: result.uuid, quantity: 1 });
			toast = `"${result.name}" ajoutée à la collection !`;
			setTimeout(() => (toast = null), 3000);
		} catch {
			toast = "Erreur lors de l'ajout.";
			setTimeout(() => (toast = null), 3000);
		} finally {
			adding = false;
		}
	}
</script>

<svelte:window onresize={syncOverlaySize} />

<div class="max-w-5xl mx-auto space-y-3 md:space-y-6 -mx-4 md:mx-auto px-0 md:px-0">

	<!-- Header — masqué sur mobile quand la caméra tourne -->
	<div class="px-4 md:px-0 {streaming ? 'hidden md:block' : ''}">
		<div class="flex items-center gap-3 text-sm text-gray-500 mb-3">
			<a href="/" class="hover:text-white transition-colors">← Dashboard</a>
			<span>/</span>
			<span>Scanner</span>
		</div>
		<div class="flex items-center justify-between flex-wrap gap-3">
			<div>
				<h1 class="text-2xl font-bold text-white">Scanner de cartes</h1>
				<p class="text-sm text-gray-500 mt-1">Identifie une carte par photo ou par caméra</p>
			</div>
		</div>
	</div>

	<!-- Boutons — toujours visibles -->
	<div class="px-4 md:px-0 flex gap-2 flex-wrap items-center justify-between">
		<div class="flex gap-2 flex-wrap">
			{#if streaming}
				<button onclick={stopCamera}
					class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-xl text-sm transition-colors">
					⏹ Arrêter
				</button>
			{:else}
				{#if cameraAvailable}
					<button onclick={startCamera}
						class="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-gray-950 font-semibold rounded-xl text-sm transition-colors">
						📷 Caméra
					</button>
				{/if}
				<label class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-xl text-sm transition-colors cursor-pointer">
					🖼 Photo
					<input type="file" accept="image/*" capture="environment" class="hidden" onchange={onFileInput} />
				</label>
			{/if}
		</div>
		{#if streaming}
			<span class="text-xs text-gray-500">Pointe vers une carte</span>
		{/if}
	</div>

	{#if !cameraAvailable && mode === 'idle'}
		<div class="mx-4 md:mx-0 bg-yellow-900/30 border border-yellow-700 rounded-xl p-3 text-yellow-300 text-sm">
			La caméra nécessite HTTPS. Accède via <strong>https://</strong> ou utilise le mode photo.
		</div>
	{/if}

	{#if error}
		<div class="mx-4 md:mx-0 bg-red-900/40 border border-red-700 rounded-xl p-4 text-red-300 text-sm">{error}</div>
	{/if}

	<div class="grid grid-cols-1 md:grid-cols-[1fr_280px] gap-4 md:gap-6">

		<!-- Flux vidéo + canvas overlay -->
		<div class="relative bg-gray-900 md:rounded-2xl overflow-hidden
			{streaming ? 'h-[70vw] max-h-[75vh] md:h-auto md:aspect-video' : 'aspect-[4/3] md:aspect-video mx-4 md:mx-0 rounded-2xl'}
			flex items-center justify-center border-0 md:border md:border-gray-700">

			{#if !streaming && mode !== 'upload'}
				<div class="text-center space-y-3 text-gray-500 px-6">
					{#if cameraAvailable}
						<p class="text-sm">Clique sur "Caméra en direct" ou charge une photo</p>
					{:else}
						<p class="text-sm">Clique sur "Charger une photo" pour identifier une carte</p>
					{/if}
				</div>
			{/if}

			{#if mode === 'upload' && scanning}
				<div class="text-center text-gray-400 space-y-2">
					<div class="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
					<p class="text-sm">Analyse en cours…</p>
				</div>
			{/if}

			<!-- svelte-ignore a11y_media_has_caption -->
			<video bind:this={videoEl}
				class="w-full h-full object-cover {streaming ? '' : 'hidden'}"
				playsinline muted>
			</video>

			<!-- Canvas overlay transparent par-dessus la vidéo -->
			<canvas bind:this={overlayCanvas}
				class="absolute inset-0 w-full h-full pointer-events-none {streaming ? '' : 'hidden'}">
			</canvas>

			<!-- Badge scan en cours -->
			{#if streaming}
				<div class="absolute top-3 right-3 flex items-center gap-2 bg-gray-950/70 backdrop-blur px-2.5 py-1 rounded-full text-xs z-10">
					<span class="w-2 h-2 rounded-full {scanning ? 'bg-amber-400 animate-pulse' : 'bg-green-500'}"></span>
					{scanning ? 'Analyse…' : `#${scanCount}`}
				</div>
			{/if}

			<!-- Nom en overlay bas -->
			{#if result && result.confidence !== 'none'}
				<div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-gray-950 to-transparent px-4 pb-4 pt-10 z-10">
					<p class="font-bold text-white text-lg leading-tight">{result.name}</p>
					<p class="text-xs mt-0.5" style="color:{CONF_COLOR[result.confidence]}">
						{CONF_LABEL[result.confidence]} · d={result.distance}/64
					</p>
				</div>
			{/if}
		</div>

		<!-- Panneau résultat -->
		<div class="space-y-4 px-4 md:px-0">
			{#if result && result.confidence !== 'none'}
				<!-- Mobile : layout horizontal (image + infos côte à côte) -->
				<div class="bg-gray-800 border border-gray-700 rounded-2xl p-4">
					<div class="flex gap-4 md:flex-col">
						<CardImage scryfallId={result.scryfall_id} alt={result.name ?? ''} size="normal"
							class="w-24 md:w-full rounded-xl shadow-lg shrink-0 self-start" />
						<div class="flex-1 min-w-0 flex flex-col gap-3">
							<div>
								<p class="font-bold text-white text-base leading-tight">{result.name}</p>
								<p class="text-xs text-gray-400 mt-0.5">{result.set_code} · {result.rarity}</p>
								{#if result.mana_cost}
									<div class="mt-1"><ManaCost cost={result.mana_cost} /></div>
								{/if}
								<p class="text-xs mt-1" style="color:{CONF_COLOR[result.confidence]}">
									{CONF_LABEL[result.confidence]}
								</p>
							</div>
							<button onclick={addCard} disabled={adding}
								class="w-full py-2.5 rounded-xl font-semibold text-sm transition-colors disabled:opacity-50
									{result.confidence === 'high'
										? 'bg-amber-500 hover:bg-amber-400 text-gray-950'
										: 'bg-gray-700 hover:bg-gray-600 text-white'}">
								{adding ? 'Ajout…' : '+ Ajouter à la collection'}
							</button>
						</div>
					</div>
				</div>
			{:else if streaming}
				<!-- Rien à afficher sur mobile quand streaming sans résultat, le guide canvas suffit -->
				<div class="hidden md:block bg-gray-800 border border-gray-700 rounded-2xl p-8 text-center text-gray-500 space-y-2">
					<p class="text-sm">Place une carte dans le champ de la caméra</p>
					<p class="text-xs text-gray-600">Le contour de la carte s'affichera quand elle sera détectée</p>
				</div>
			{/if}
		</div>
	</div>
</div>

<!-- Canvas caché pour la capture des frames -->
<canvas bind:this={captureCanvas} class="hidden"></canvas>

{#if toast}
	<div class="fixed bottom-6 right-6 bg-green-700 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-medium">
		{toast}
	</div>
{/if}
