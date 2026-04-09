/* ============================================================
   DNA Analyzer — Chart.js Visualizations
   ============================================================ */

const DNACharts = (() => {
    const SEVERITY_COLORS = {
        CRITICAL:   '#DC2626',
        HIGH:       '#EA580C',
        MODERATE:   '#D97706',
        LOW:        '#2563EB',
        PROTECTIVE: '#059669',
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
                    font: { family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', size: 12 },
                    padding: 14,
                    usePointStyle: true,
                    pointStyleWidth: 10,
                },
            },
            tooltip: {
                backgroundColor: '#1F2937',
                titleFont: { size: 13, weight: '600' },
                bodyFont: { size: 12 },
                padding: 10,
                cornerRadius: 6,
                displayColors: true,
            },
        },
    };

    // Track chart instances for cleanup
    const instances = {};

    function destroy(id) {
        if (instances[id]) {
            instances[id].destroy();
            delete instances[id];
        }
    }

    /**
     * Severity donut chart for the Overview tab.
     */
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
            colors.push('#E5E7EB');
        }

        const chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{
                    data,
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: '#FFFFFF',
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

    /**
     * Horizontal stacked bar chart for ancestry composition.
     */
    function createAncestryBar(canvasId, composition) {
        destroy(canvasId);
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        const regionColors = [
            '#2563EB', '#7C3AED', '#059669', '#D97706', '#DC2626',
            '#EC4899', '#0891B2', '#65A30D', '#EA580C', '#6366F1',
            '#14B8A6', '#F59E0B', '#8B5CF6', '#10B981',
        ];

        const labels = composition.map(c => c.region || c.name);
        const data = composition.map(c => c.percentage);
        const colors = composition.map((_, i) => regionColors[i % regionColors.length]);

        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    data,
                    backgroundColor: colors,
                    borderRadius: 4,
                    barThickness: 28,
                }],
            },
            options: {
                ...chartDefaults,
                indexAxis: 'y',
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { callback: v => v + '%', font: { size: 11 } },
                        grid: { color: '#F3F4F6' },
                    },
                    y: {
                        ticks: { font: { size: 12, weight: '600' } },
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

    /**
     * Semi-circular gauge for PRS percentiles.
     * Returns a canvas-based gauge drawn manually (no Chart.js dependency for this one).
     */
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
        ctx.strokeStyle = '#E5E7EB';
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
        ctx.fillStyle = '#1F2937';
        ctx.font = 'bold 28px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.fillText(`${Math.round(percentile)}%`, cx, cy - 10);

        ctx.font = '12px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.fillStyle = '#9CA3AF';
        ctx.fillText('percentile', cx, cy + 10);

        return canvas;
    }

    /**
     * Population frequency comparison bar (simple horizontal).
     */
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
