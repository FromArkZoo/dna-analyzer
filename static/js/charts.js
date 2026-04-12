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

    // SVG World Map for ancestry composition
    function createWorldMap(containerId, composition) {
        const container = document.getElementById(containerId);
        if (!container) return null;

        // Build a lookup from region name to percentage
        const regionData = {};
        (composition || []).forEach(c => {
            const name = (c.region || c.population || c.name || '').toLowerCase();
            regionData[name] = c.percentage || 0;
        });

        // Match region names to our simplified paths
        function getOpacity(regionKeys) {
            let maxPct = 0;
            for (const k of regionKeys) {
                for (const [name, pct] of Object.entries(regionData)) {
                    if (name.includes(k) || k.includes(name)) {
                        maxPct = Math.max(maxPct, pct);
                    }
                }
            }
            return maxPct > 0 ? Math.max(0.15, Math.min(1, maxPct / 60)) : 0.05;
        }

        // Simplified continent/region outlines as SVG paths
        const regions = [
            { keys: ['northern europe', 'western europe', 'british', 'scandinavian', 'northwest europe'],
              color: '#4a6fa5',
              path: 'M 460,95 L 480,80 L 510,75 L 530,85 L 520,105 L 500,115 L 475,110 Z' },
            { keys: ['southern europe', 'mediterranean', 'italian', 'iberian'],
              color: '#7a5ca8',
              path: 'M 450,115 L 475,110 L 500,115 L 510,130 L 490,140 L 460,135 Z' },
            { keys: ['eastern europe', 'slavic', 'baltic', 'ashkenazi'],
              color: '#3a8e9e',
              path: 'M 520,80 L 560,75 L 580,95 L 570,115 L 530,120 L 520,105 Z' },
            { keys: ['east asia', 'chinese', 'japanese', 'korean', 'southeast asia'],
              color: '#9e8230',
              path: 'M 680,100 L 730,90 L 760,100 L 770,130 L 740,150 L 700,145 L 680,125 Z' },
            { keys: ['south asia', 'indian', 'south asian'],
              color: '#a05a8a',
              path: 'M 640,130 L 670,120 L 690,135 L 680,160 L 655,170 L 635,155 Z' },
            { keys: ['sub-saharan', 'west africa', 'east africa', 'african', 'nigerian', 'central africa'],
              color: '#3d8b63',
              path: 'M 440,170 L 480,155 L 530,160 L 545,200 L 530,240 L 500,255 L 465,245 L 440,210 Z' },
            { keys: ['near east', 'middle east', 'north africa', 'arab', 'levantine'],
              color: '#b8652e',
              path: 'M 520,125 L 560,120 L 600,130 L 610,155 L 580,160 L 540,155 L 520,140 Z' },
            { keys: ['indigenous', 'native american', 'americas', 'mesoamerican'],
              color: '#c0392b',
              path: 'M 150,100 L 200,80 L 230,110 L 240,160 L 220,200 L 190,220 L 160,200 L 140,160 Z' },
            { keys: ['south america', 'andean'],
              color: '#c0392b',
              path: 'M 230,220 L 260,210 L 280,240 L 275,300 L 250,330 L 230,310 L 220,260 Z' },
            { keys: ['oceania', 'melanesian', 'polynesian', 'australian aboriginal'],
              color: '#5a5aa8',
              path: 'M 740,230 L 790,220 L 820,240 L 810,270 L 770,280 L 740,260 Z' },
        ];

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 900 380');
        svg.setAttribute('width', '100%');
        svg.setAttribute('height', '100%');
        svg.style.maxWidth = '100%';
        svg.style.borderRadius = '0.5rem';

        // Background
        let svgContent = `<rect width="900" height="380" fill="rgba(15,25,35,0.9)" rx="8"/>`;

        // Grid lines for decoration
        for (let x = 0; x < 900; x += 60) {
            svgContent += `<line x1="${x}" y1="0" x2="${x}" y2="380" stroke="rgba(255,255,255,0.03)" stroke-width="0.5"/>`;
        }
        for (let y = 0; y < 380; y += 60) {
            svgContent += `<line x1="0" y1="${y}" x2="900" y2="${y}" stroke="rgba(255,255,255,0.03)" stroke-width="0.5"/>`;
        }

        // Render regions
        regions.forEach(r => {
            const opacity = getOpacity(r.keys);
            svgContent += `<path d="${r.path}" fill="${r.color}" opacity="${opacity}" stroke="rgba(255,255,255,0.15)" stroke-width="0.5"/>`;

            // If region has significant data, add a glow
            if (opacity > 0.3) {
                svgContent += `<path d="${r.path}" fill="${r.color}" opacity="${opacity * 0.3}" filter="url(#glow)" stroke="none"/>`;
            }
        });

        // Add glow filter definition
        svgContent = `
            <defs>
                <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
                    <feGaussianBlur stdDeviation="8" result="blur"/>
                    <feMerge>
                        <feMergeNode in="blur"/>
                        <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                </filter>
            </defs>
        ` + svgContent;

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
