/* ============================================================
   DNA Analyzer — Chart.js Visualizations (glass theme)
   ============================================================ */

const DNACharts = (() => {
    const SEVERITY_COLORS = {
        CRITICAL:   '#c0392b',
        HIGH:       '#b8652e',
        MODERATE:   '#9e8230',
        LOW:        '#4a6fa5',
        PROTECTIVE: '#3d8b63',
    };

    const SEVERITY_LABELS = {
        CRITICAL: 'Critical',
        HIGH: 'High',
        MODERATE: 'Moderate',
        LOW: 'Low',
        PROTECTIVE: 'Protective',
    };

    const chartDefaults = {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: {
                labels: {
                    font: { family: "'Inter', sans-serif", size: 12 },
                    color: 'rgba(68,71,72,0.8)',
                    padding: 14,
                    usePointStyle: true,
                    pointStyleWidth: 10,
                },
            },
            tooltip: {
                backgroundColor: 'rgba(11, 16, 18, 0.92)',
                titleFont: { size: 13, weight: '600', family: "'Inter', sans-serif" },
                bodyFont: { size: 12, family: "'Inter', sans-serif" },
                titleColor: '#f9f9fb',
                bodyColor: 'rgba(249,249,251,0.8)',
                borderColor: 'rgba(0,0,0,0.1)',
                borderWidth: 1,
                padding: 12,
                cornerRadius: 4,
                displayColors: true,
            },
        },
    };

    const instances = {};

    function destroy(id) {
        if (instances[id]) {
            instances[id].destroy();
            delete instances[id];
        }
    }

    function createSeverityDonut(canvasId, counts) {
        destroy(canvasId);
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        const labels = [];
        const data = [];
        const colors = [];

        for (const sev of ['CRITICAL', 'HIGH', 'MODERATE', 'LOW', 'PROTECTIVE']) {
            const val = counts[sev] || 0;
            if (val > 0) {
                labels.push(SEVERITY_LABELS[sev]);
                data.push(val);
                colors.push(SEVERITY_COLORS[sev]);
            }
        }

        if (data.length === 0) {
            labels.push('No findings');
            data.push(1);
            colors.push('rgba(0,0,0,0.06)');
        }

        const chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{
                    data,
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: 'rgba(255,255,255,0.6)',
                    hoverBorderWidth: 3,
                }],
            },
            options: {
                ...chartDefaults,
                cutout: '62%',
                plugins: {
                    ...chartDefaults.plugins,
                    legend: {
                        ...chartDefaults.plugins.legend,
                        position: 'bottom',
                    },
                },
            },
        });
        instances[canvasId] = chart;
        return chart;
    }

    function createAncestryBar(canvasId, composition) {
        destroy(canvasId);
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        const regionColors = [
            '#4a6fa5', '#7a5ca8', '#3d8b63', '#9e8230', '#c0392b',
            '#a05a8a', '#3a8e9e', '#6a8e4a', '#b8652e', '#5a5aa8',
            '#3a9e8e', '#9e8230', '#7a5ca8', '#3d8b63',
        ];

        const labels = composition.map(c => c.region || c.population || c.name);
        const data = composition.map(c => c.percentage);
        const colors = composition.map((_, i) => regionColors[i % regionColors.length]);

        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    data,
                    backgroundColor: colors,
                    borderRadius: 2,
                    barThickness: 24,
                }],
            },
            options: {
                ...chartDefaults,
                indexAxis: 'y',
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: v => v + '%',
                            font: { size: 11, family: "'Inter', sans-serif" },
                            color: 'rgba(68,71,72,0.6)',
                        },
                        grid: { color: 'rgba(0,0,0,0.04)' },
                    },
                    y: {
                        ticks: {
                            font: { size: 12, weight: '600', family: "'Inter', sans-serif" },
                            color: 'rgba(68,71,72,0.8)',
                        },
                        grid: { display: false },
                    },
                },
                plugins: {
                    ...chartDefaults.plugins,
                    legend: { display: false },
                    tooltip: {
                        ...chartDefaults.plugins.tooltip,
                        callbacks: {
                            label: ctx => `${ctx.parsed.x.toFixed(1)}%`,
                        },
                    },
                },
            },
        });
        instances[canvasId] = chart;
        return chart;
    }

    // Legacy canvas PRS gauge (kept for backwards compat)
    function createPRSGauge(container, percentile, condition) {
        return createPRSGaugeSVG(container, percentile, condition);
    }

    // SVG-based PRS gauge for glass panels
    function createPRSGaugeSVG(container, percentile, condition) {
        const pct = Math.max(0, Math.min(100, percentile));
        const cx = 100, cy = 90, radius = 70;
        const startAngle = Math.PI;
        const sweepAngle = (pct / 100) * Math.PI;

        let color;
        if (pct >= 80) color = SEVERITY_COLORS.CRITICAL;
        else if (pct >= 60) color = SEVERITY_COLORS.HIGH;
        else if (pct >= 40) color = SEVERITY_COLORS.MODERATE;
        else color = SEVERITY_COLORS.PROTECTIVE;

        // Arc path helper
        function describeArc(cx, cy, r, startAngle, endAngle) {
            const x1 = cx + r * Math.cos(startAngle);
            const y1 = cy + r * Math.sin(startAngle);
            const x2 = cx + r * Math.cos(endAngle);
            const y2 = cy + r * Math.sin(endAngle);
            const largeArc = endAngle - startAngle > Math.PI ? 1 : 0;
            return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`;
        }

        const bgArc = describeArc(cx, cy, radius, Math.PI, 2 * Math.PI);
        const fillArc = pct > 0 ? describeArc(cx, cy, radius, Math.PI, Math.PI + sweepAngle) : '';

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 200 110');
        svg.setAttribute('width', '200');
        svg.setAttribute('height', '110');
        svg.style.display = 'block';
        svg.style.margin = '0 auto';

        svg.innerHTML = `
            <path d="${bgArc}" fill="none" stroke="rgba(0,0,0,0.06)" stroke-width="16" stroke-linecap="round"/>
            ${fillArc ? `<path d="${fillArc}" fill="none" stroke="${color}" stroke-width="16" stroke-linecap="round"/>` : ''}
            <text x="${cx}" y="${cy - 8}" text-anchor="middle" font-family="Inter, sans-serif" font-size="24" font-weight="bold" fill="#1a1c1e">${Math.round(pct)}%</text>
            <text x="${cx}" y="${cy + 10}" text-anchor="middle" font-family="Inter, sans-serif" font-size="8" font-weight="600" fill="rgba(68,71,72,0.6)" letter-spacing="0.1em">PERCENTILE</text>
        `;

        container.appendChild(svg);
        return svg;
    }

    // SVG World Map for ancestry composition — recognizable geography
    function createWorldMap(containerId, composition) {
        const container = document.getElementById(containerId);
        if (!container) return null;

        const regionData = {};
        (composition || []).forEach(c => {
            const name = (c.region || c.population || c.name || '').toLowerCase();
            regionData[name] = c.percentage || 0;
        });

        function matchPct(keys) {
            let maxPct = 0, matchedName = '';
            for (const k of keys) {
                for (const [name, pct] of Object.entries(regionData)) {
                    if (name.includes(k) || k.includes(name)) {
                        if (pct > maxPct) { maxPct = pct; matchedName = name; }
                    }
                }
            }
            return { pct: maxPct, name: matchedName };
        }

        // Continent outlines (subtle base layer)
        const continentOutlines = [
            'M85,70 L110,55 L145,48 L170,45 L195,50 L220,58 L235,52 L250,48 L255,55 L248,65 L238,72 L230,80 L225,95 L228,108 L235,120 L240,135 L248,148 L255,160 L258,172 L252,178 L242,175 L232,168 L220,165 L210,170 L200,180 L192,175 L185,168 L175,162 L168,155 L160,150 L148,148 L138,142 L128,135 L118,125 L108,115 L98,105 L90,92 L85,80 Z',
            'M218,195 L228,188 L240,185 L252,190 L262,200 L270,215 L275,232 L278,252 L276,272 L272,292 L265,310 L258,325 L250,338 L240,345 L232,342 L225,332 L220,318 L216,300 L214,280 L212,260 L213,240 L215,220 L216,205 Z',
            'M440,55 L450,50 L462,48 L472,52 L478,48 L485,42 L492,40 L498,45 L502,52 L508,55 L515,52 L522,48 L530,50 L535,56 L540,62 L542,70 L538,78 L530,82 L524,88 L520,95 L518,102 L515,108 L510,112 L505,118 L498,122 L492,128 L488,134 L482,138 L475,140 L468,138 L460,135 L454,130 L448,126 L443,120 L440,114 L436,108 L435,100 L434,92 L432,84 L434,75 L436,65 Z',
            'M432,68 L436,62 L440,58 L444,60 L446,66 L444,72 L440,76 L436,74 Z M428,76 L432,74 L435,78 L436,84 L434,90 L430,92 L426,88 L426,82 Z',
            'M448,148 L460,142 L475,140 L490,142 L505,144 L518,148 L528,152 L538,158 L545,165 L548,175 L550,185 L548,198 L542,210 L538,222 L535,235 L530,248 L525,260 L518,272 L510,282 L502,290 L492,296 L482,298 L472,296 L462,290 L455,280 L450,268 L446,255 L444,240 L442,225 L440,210 L438,195 L435,180 L434,168 L436,158 L440,150 Z',
            'M540,110 L555,108 L570,112 L582,118 L590,126 L595,138 L592,148 L585,155 L575,158 L565,160 L555,155 L548,148 L542,140 L538,130 L536,120 Z',
            'M600,100 L620,95 L640,98 L655,105 L665,115 L668,128 L665,140 L658,152 L648,162 L638,170 L628,175 L618,172 L610,165 L605,155 L602,142 L600,128 L598,115 Z',
            'M660,65 L680,58 L700,60 L718,68 L732,78 L740,92 L742,108 L738,122 L730,135 L718,145 L705,150 L692,152 L680,148 L670,140 L662,130 L656,118 L652,105 L650,90 L652,78 Z',
            'M680,158 L695,155 L710,160 L720,170 L725,182 L722,195 L712,205 L698,210 L685,208 L675,200 L670,188 L672,175 Z',
            'M540,62 L560,55 L585,50 L612,48 L640,50 L665,55 L690,52 L710,48 L730,50 L745,55 L755,62 L758,72 L750,78 L740,82 L728,80 L718,75 L700,68 L680,65 L660,65 L652,78 L650,68 L640,62 L620,58 L600,55 L580,58 L560,62 L545,68 L540,75 L535,70 Z',
            'M740,265 L755,258 L772,255 L790,258 L805,265 L812,278 L810,292 L802,302 L790,308 L775,310 L760,306 L750,298 L744,285 L742,275 Z',
        ];

        // Ancestry regions overlaid on continents
        const ancestryRegions = [
            { keys:['british','irish'], color:'#4a6fa5', label:[438,75],
              path:'M432,68 L436,62 L440,58 L444,60 L446,66 L444,72 L440,76 L436,74 Z M428,76 L432,74 L435,78 L436,84 L434,90 L430,92 L426,88 L426,82 Z' },
            { keys:['nw european','northwest','french','german','dutch'], color:'#5a7fb5', label:[475,105],
              path:'M455,88 L465,82 L478,80 L488,84 L495,92 L498,102 L495,112 L488,118 L478,120 L468,118 L458,112 L452,102 L452,95 Z' },
            { keys:['scandinavian','finnish','nordic','norwegian','swedish'], color:'#3a6e95', label:[488,55],
              path:'M472,52 L478,48 L485,42 L492,40 L498,45 L502,52 L508,55 L515,52 L522,48 L530,50 L535,56 L530,62 L522,58 L515,55 L508,58 L502,62 L498,65 L492,68 L485,72 L478,68 L474,62 Z' },
            { keys:['southern european','italian','iberian','greek','spanish','mediterranean'], color:'#7a5ca8', label:[470,135],
              path:'M443,120 L452,116 L462,118 L472,120 L482,124 L490,128 L498,126 L505,130 L508,138 L502,144 L492,146 L480,145 L468,142 L456,138 L448,132 L443,126 Z' },
            { keys:['eastern european','slavic','baltic','polish','russian','ashkenazi'], color:'#3a8e9e', label:[535,85],
              path:'M515,55 L525,52 L535,56 L542,65 L545,75 L542,85 L538,95 L532,102 L525,108 L518,112 L510,108 L505,100 L502,92 L505,82 L508,72 L510,62 Z' },
            { keys:['near east','middle east','arab','levantine','turkish'], color:'#b8652e', label:[568,135],
              path:'M540,110 L555,108 L570,112 L582,118 L590,126 L595,138 L592,148 L585,155 L575,158 L565,160 L555,155 L548,148 L542,140 L538,130 L536,120 Z' },
            { keys:['north africa','berber','egyptian','maghreb'], color:'#c4873e', label:[478,155],
              path:'M448,148 L460,142 L475,140 L490,142 L505,144 L518,148 L528,152 L535,158 L530,165 L518,168 L505,170 L490,172 L475,170 L460,168 L450,162 L446,155 Z' },
            { keys:['sub-saharan','west africa','east africa','african','nigerian','central africa'], color:'#3d8b63', label:[490,235],
              path:'M450,172 L465,170 L480,172 L495,175 L510,178 L525,182 L535,190 L540,202 L538,218 L532,232 L525,245 L518,258 L508,270 L498,278 L488,282 L478,280 L468,274 L460,264 L455,250 L450,235 L448,218 L446,200 L445,185 Z' },
            { keys:['south asia','indian','south asian','pakistani'], color:'#a05a8a', label:[630,145],
              path:'M608,115 L620,108 L635,112 L648,120 L655,132 L652,145 L645,158 L635,168 L625,172 L615,168 L608,158 L604,145 L602,132 L604,122 Z' },
            { keys:['east asia','chinese','japanese','korean','han'], color:'#9e8230', label:[700,105],
              path:'M670,72 L688,68 L705,72 L720,80 L730,92 L735,108 L730,122 L720,132 L708,138 L695,140 L682,136 L672,128 L665,118 L660,105 L658,92 L662,80 Z' },
            { keys:['southeast asia','filipino','vietnamese','thai','malay'], color:'#8e7a30', label:[698,182],
              path:'M680,158 L695,155 L710,160 L720,170 L725,182 L722,195 L712,205 L698,210 L685,208 L675,200 L670,188 L672,175 Z' },
            { keys:['native american','indigenous','mesoamerican','americas'], color:'#c0392b', label:[190,120],
              path:'M108,70 L135,60 L165,55 L195,58 L218,68 L232,80 L240,95 L245,112 L248,130 L245,148 L238,162 L225,170 L210,168 L198,160 L185,150 L172,140 L158,128 L145,118 L132,108 L120,95 L110,82 Z' },
            { keys:['south america','andean','brazilian'], color:'#c0392b', label:[248,270],
              path:'M218,195 L228,188 L240,185 L252,190 L262,200 L270,215 L275,232 L278,252 L276,272 L272,292 L265,310 L258,325 L250,338 L240,345 L232,342 L225,332 L220,318 L216,300 L214,280 L212,260 L213,240 L215,220 L216,205 Z' },
            { keys:['oceania','melanesian','polynesian','australian','aboriginal'], color:'#5a5aa8', label:[775,285],
              path:'M740,265 L755,258 L772,255 L790,258 L805,265 L812,278 L810,292 L802,302 L790,308 L775,310 L760,306 L750,298 L744,285 L742,275 Z' },
        ];

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 1000 500');
        svg.setAttribute('width', '100%');
        svg.setAttribute('height', '100%');
        svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
        svg.style.maxWidth = '100%';
        svg.style.borderRadius = '0.75rem';

        let svgContent = `<rect width="1000" height="500" fill="rgba(235,245,255,0.5)" rx="12"/>`;

        // Latitude lines
        [125, 250, 375].forEach(y => {
            svgContent += `<line x1="30" y1="${y}" x2="970" y2="${y}" stroke="rgba(0,0,0,0.04)" stroke-width="0.5" stroke-dasharray="4,4"/>`;
        });

        // Draw continent outlines (subtle gray)
        continentOutlines.forEach(p => {
            svgContent += `<path d="${p}" fill="rgba(0,0,0,0.04)" stroke="rgba(0,0,0,0.08)" stroke-width="0.5" stroke-linejoin="round"/>`;
        });

        // Draw highlighted ancestry regions
        const labels = [];
        ancestryRegions.forEach(r => {
            const m = matchPct(r.keys);
            const pct = m.pct;
            const opacity = pct > 0 ? Math.max(0.3, Math.min(0.8, pct / 30)) : 0;
            if (opacity > 0) {
                svgContent += `<path d="${r.path}" fill="${r.color}" fill-opacity="${opacity}" stroke="${r.color}" stroke-width="1.5" stroke-linejoin="round"/>`;
                const displayName = m.name.replace(/\b\w/g, c => c.toUpperCase());
                labels.push({ x: r.label[0], y: r.label[1], text: displayName, pct: Math.round(pct * 10) / 10, color: r.color });
            }
        });

        // Labels with white pill badges
        labels.forEach(l => {
            const tw = Math.max(l.text.length * 5 + 30, 55);
            svgContent += `<rect x="${l.x - tw/2}" y="${l.y - 9}" width="${tw}" height="18" rx="9" fill="white" fill-opacity="0.92" stroke="${l.color}" stroke-width="0.8"/>`;
            svgContent += `<text x="${l.x}" y="${l.y + 3.5}" text-anchor="middle" font-family="Inter,sans-serif" font-size="7" font-weight="700" fill="${l.color}">${l.text} ${l.pct}%</text>`;
        });

        svg.innerHTML = svgContent;
        container.innerHTML = '';
        container.appendChild(svg);
        return svg;
    }

    function createPopFreqBar(container, frequency) {
        const pct = Math.min(100, Math.max(0, (frequency || 0) * 100));
        const bar = document.createElement('div');
        bar.className = 'population-freq-bar';
        bar.innerHTML = `<div class="population-freq-fill" style="width:${pct}%"></div>`;
        container.appendChild(bar);
        return bar;
    }

    function destroyAll() {
        for (const id of Object.keys(instances)) {
            destroy(id);
        }
    }

    return {
        createSeverityDonut,
        createAncestryBar,
        createPRSGauge,
        createPRSGaugeSVG,
        createWorldMap,
        createPopFreqBar,
        destroyAll,
        SEVERITY_COLORS,
        SEVERITY_LABELS,
    };
})();
