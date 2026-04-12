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

    // SVG World Map using real GeoJSON-derived country boundaries
    function createWorldMap(containerId, composition) {
        const container = document.getElementById(containerId);
        if (!container) return null;
        if (typeof WORLD_MAP_DATA === 'undefined') return null;

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

        // Region config: keys for matching, color, label position
        const regionConfig = [
            { id:'british', keys:['british','irish'], color:'#4a6fa5', lx:370, ly:115, cx:462, cy:110 },
            { id:'nw-europe', keys:['nw european','northwest','french','german','dutch'], color:'#5a7fb5', lx:370, ly:140, cx:478, cy:132 },
            { id:'scandinavia', keys:['scandinavian','finnish','nordic','norwegian','swedish'], color:'#3a6e95', lx:560, ly:65, cx:500, cy:82 },
            { id:'south-europe', keys:['southern european','italian','iberian','greek','spanish','mediterranean'], color:'#7a5ca8', lx:370, ly:165, cx:480, cy:148 },
            { id:'east-europe', keys:['eastern european','slavic','baltic','polish','russian','ashkenazi'], color:'#3a8e9e', lx:600, ly:100, cx:535, cy:110 },
            { id:'middle-east', keys:['near east','middle east','arab','levantine','turkish'], color:'#b8652e', lx:620, ly:170, cx:570, cy:145 },
            { id:'north-africa', keys:['north africa','berber','egyptian','maghreb'], color:'#c4873e', lx:420, ly:195, cx:490, cy:165 },
            { id:'sub-saharan', keys:['sub-saharan','west africa','east africa','african','nigerian','central africa'], color:'#3d8b63', lx:420, ly:275, cx:500, cy:240 },
            { id:'south-asia', keys:['south asia','indian','south asian','pakistani'], color:'#a05a8a', lx:690, ly:195, cx:640, cy:170 },
            { id:'east-asia', keys:['east asia','chinese','japanese','korean','han'], color:'#9e8230', lx:760, ly:130, cx:710, cy:120 },
            { id:'southeast-asia', keys:['southeast asia','filipino','vietnamese','thai','malay'], color:'#8e7a30', lx:760, ly:210, cx:700, cy:195 },
            { id:'central-asia', keys:['central asia','steppe','turkic','mongol'], color:'#7a8e5a', lx:680, ly:90, cx:620, cy:100 },
            { id:'north-america', keys:['native american','indigenous','mesoamerican','americas'], color:'#c0392b', lx:120, ly:155, cx:185, cy:120 },
            { id:'central-america', keys:['central america','mexican','caribbean'], color:'#d04a3a', lx:160, ly:210, cx:220, cy:185 },
            { id:'south-america', keys:['south america','andean','brazilian'], color:'#c0392b', lx:200, ly:320, cx:260, cy:280 },
            { id:'oceania', keys:['oceania','melanesian','polynesian','australian','aboriginal'], color:'#5a5aa8', lx:850, ly:320, cx:790, cy:300 },
            { id:'russia', keys:['siberian','north asian'], color:'#6a8a6a', lx:700, ly:55, cx:650, cy:72 },
        ];

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 1000 500');
        svg.setAttribute('width', '100%');
        svg.setAttribute('height', '100%');
        svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
        svg.style.maxWidth = '100%';
        svg.style.borderRadius = '0.75rem';

        // Background
        let svgContent = `<rect width="1000" height="500" fill="rgba(235,245,255,0.4)" rx="12"/>`;

        // Latitude/longitude grid
        [125, 250, 375].forEach(y => {
            svgContent += `<line x1="20" y1="${y}" x2="980" y2="${y}" stroke="rgba(0,0,0,0.03)" stroke-width="0.5" stroke-dasharray="4,4"/>`;
        });
        [200, 400, 600, 800].forEach(x => {
            svgContent += `<line x1="${x}" y1="20" x2="${x}" y2="480" stroke="rgba(0,0,0,0.02)" stroke-width="0.5" stroke-dasharray="4,4"/>`;
        });

        // Draw all country outlines (subtle gray base)
        WORLD_MAP_DATA.allPaths.forEach(p => {
            svgContent += `<path d="${p}" fill="rgba(200,210,220,0.35)" stroke="rgba(255,255,255,0.8)" stroke-width="0.5" stroke-linejoin="round"/>`;
        });

        // Overlay highlighted ancestry regions
        const labels = [];
        regionConfig.forEach(r => {
            const regionPath = WORLD_MAP_DATA.regions[r.id];
            if (!regionPath) return;

            const m = matchPct(r.keys);
            const pct = m.pct;
            const opacity = pct > 0 ? Math.max(0.35, Math.min(0.85, pct / 28)) : 0;

            if (opacity > 0) {
                svgContent += `<path d="${regionPath}" fill="${r.color}" fill-opacity="${opacity}" stroke="${r.color}" stroke-opacity="0.6" stroke-width="1" stroke-linejoin="round"/>`;
                const displayName = m.name.replace(/\b\w/g, c => c.toUpperCase());
                labels.push({ x: r.lx, y: r.ly, ox: r.lx, oy: r.ly, cx: r.cx, cy: r.cy, text: displayName, pct: Math.round(pct * 10) / 10, color: r.color });
            }
        });

        // De-crowd labels: push overlapping labels apart vertically
        labels.sort((a, b) => a.y - b.y);
        const labelH = 22;
        for (let i = 1; i < labels.length; i++) {
            for (let j = 0; j < i; j++) {
                const dx = Math.abs(labels[i].x - labels[j].x);
                const dy = labels[i].y - labels[j].y;
                if (dx < 120 && Math.abs(dy) < labelH) {
                    labels[i].y = labels[j].y + labelH;
                }
            }
        }

        // Render connector lines + labels
        labels.forEach(l => {
            const tw = Math.max(l.text.length * 5.2 + 32, 58);

            // Connector line from label edge to region center dot
            const lineStartX = l.x + (l.cx > l.x ? tw/2 : -tw/2);
            const lineStartY = l.y;
            svgContent += `<line x1="${lineStartX}" y1="${lineStartY}" x2="${l.cx}" y2="${l.cy}" stroke="${l.color}" stroke-opacity="0.35" stroke-width="1" stroke-dasharray="3,2"/>`;
            // Dot at region center
            svgContent += `<circle cx="${l.cx}" cy="${l.cy}" r="3.5" fill="${l.color}" fill-opacity="0.7" stroke="white" stroke-width="1"/>`;

            // Label pill
            svgContent += `<rect x="${l.x - tw/2}" y="${l.y - 10}" width="${tw}" height="20" rx="10" fill="white" fill-opacity="0.95" stroke="${l.color}" stroke-width="1"/>`;
            svgContent += `<text x="${l.x}" y="${l.y + 4}" text-anchor="middle" font-family="Inter,sans-serif" font-size="7.5" font-weight="700" fill="${l.color}">${l.text} ${l.pct}%</text>`;
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
