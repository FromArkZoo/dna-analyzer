/* ============================================================
   DNA Analyzer — Chart.js Visualizations (light theme)
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
                    color: 'rgba(11, 16, 18, 0.55)',
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
                    borderColor: '#f3f3f6',
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
                            color: 'rgba(11, 16, 18, 0.45)',
                        },
                        grid: { color: 'rgba(0,0,0,0.04)' },
                    },
                    y: {
                        ticks: {
                            font: { size: 12, weight: '600', family: "'Inter', sans-serif" },
                            color: '#1a1c1e',
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

    function createPRSGauge(container, percentile, condition) {
        const canvas = document.createElement('canvas');
        canvas.width = 280;
        canvas.height = 160;
        container.appendChild(canvas);

        const ctx = canvas.getContext('2d');
        const cx = 140, cy = 130, radius = 100;
        const startAngle = Math.PI;
        const endAngle = 2 * Math.PI;
        const pct = Math.max(0, Math.min(100, percentile)) / 100;

        // Background arc
        ctx.beginPath();
        ctx.arc(cx, cy, radius, startAngle, endAngle);
        ctx.lineWidth = 22;
        ctx.strokeStyle = 'rgba(0,0,0,0.06)';
        ctx.lineCap = 'round';
        ctx.stroke();

        // Colored arc
        const fillEnd = startAngle + pct * Math.PI;
        let color;
        if (percentile >= 80) color = SEVERITY_COLORS.CRITICAL;
        else if (percentile >= 60) color = SEVERITY_COLORS.HIGH;
        else if (percentile >= 40) color = SEVERITY_COLORS.MODERATE;
        else color = SEVERITY_COLORS.PROTECTIVE;

        ctx.beginPath();
        ctx.arc(cx, cy, radius, startAngle, fillEnd);
        ctx.lineWidth = 22;
        ctx.strokeStyle = color;
        ctx.lineCap = 'round';
        ctx.stroke();

        // Percentile text
        ctx.textAlign = 'center';
        ctx.fillStyle = '#1a1c1e';
        ctx.font = "bold 28px 'Inter', sans-serif";
        ctx.fillText(`${Math.round(percentile)}%`, cx, cy - 10);

        ctx.font = "600 10px 'Inter', sans-serif";
        ctx.fillStyle = 'rgba(11, 16, 18, 0.45)';
        ctx.letterSpacing = '0.08em';
        ctx.fillText('PERCENTILE', cx, cy + 10);

        return canvas;
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
        createPopFreqBar,
        destroyAll,
        SEVERITY_COLORS,
        SEVERITY_LABELS,
    };
})();
