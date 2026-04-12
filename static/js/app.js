/* ============================================================
   DNA Analyzer — Main Application Logic
   ============================================================ */

let analysisData = null;

// ---- Sections ----
const $upload   = () => document.getElementById('upload-section');
const $loading  = () => document.getElementById('loading-section');
const $results  = () => document.getElementById('results-section');
const $actions  = () => document.getElementById('header-actions');

// ---- Show / hide helpers ----
function showSection(id) {
    ['upload-section', 'loading-section', 'results-section'].forEach(s => {
        document.getElementById(s).style.display = s === id ? '' : 'none';
    });
    $actions().style.display = id === 'results-section' ? '' : 'none';
    // Show/hide fixed bottom tab nav independently
    const tabNav = document.getElementById('tab-nav');
    if (tabNav) tabNav.style.display = id === 'results-section' ? 'flex' : 'none';
}

function resetApp() {
    analysisData = null;
    DNACharts.destroyAll();
    showSection('upload-section');
    window.location.hash = '';
}

// ---- File Upload ----
(function initUpload() {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    if (!dropzone || !fileInput) return;

    dropzone.addEventListener('click', () => fileInput.click());
    dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('dragover'); });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
    dropzone.addEventListener('drop', e => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) handleFile(fileInput.files[0]);
    });
})();

// Header glass effect on scroll
window.addEventListener('scroll', () => {
    const header = document.querySelector('.glass-nav');
    if (!header) {
        const fallback = document.querySelector('.app-header');
        if (fallback) fallback.classList.toggle('scrolled', window.scrollY > 40);
    } else {
        header.classList.toggle('scrolled', window.scrollY > 40);
    }
}, { passive: true });

function handleFile(file) {
    const errEl = document.getElementById('upload-error');
    errEl.style.display = 'none';

    const validExt = ['.txt', '.csv', '.tsv', '.zip'];
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!validExt.includes(ext)) {
        errEl.textContent = `Unsupported file type "${ext}". Please upload a .txt, .csv, .tsv, or .zip file.`;
        errEl.style.display = '';
        return;
    }
    if (file.size > 64 * 1024 * 1024) {
        errEl.textContent = 'File is too large (max 64 MB).';
        errEl.style.display = '';
        return;
    }

    uploadFile(file);
}

async function uploadFile(file) {
    showSection('loading-section');
    const statusEl = document.getElementById('loading-status');
    const progressEl = document.getElementById('progress-fill');

    // Simulate progress
    let pct = 0;
    const messages = [
        [10, 'Uploading file...'],
        [30, 'Parsing genotype data...'],
        [50, 'Matching variants to database...'],
        [70, 'Analyzing health risks...'],
        [85, 'Computing pharmacogenomics...'],
        [95, 'Generating report...'],
    ];
    const progressInterval = setInterval(() => {
        if (pct < 95) {
            pct += 1;
            progressEl.style.width = pct + '%';
            for (const [threshold, msg] of messages) {
                if (pct === threshold) statusEl.textContent = msg;
            }
        }
    }, 120);

    try {
        const formData = new FormData();
        formData.append('file', file);

        const resp = await fetch('/api/analyze', {
            method: 'POST',
            body: formData,
        });

        clearInterval(progressInterval);

        if (!resp.ok) {
            const errBody = await resp.json().catch(() => ({}));
            throw new Error(errBody.error || `Server error (${resp.status})`);
        }

        analysisData = await resp.json();
        progressEl.style.width = '100%';
        statusEl.textContent = 'Analysis complete!';

        setTimeout(() => {
            showSection('results-section');
            renderResults(analysisData);
            window.location.hash = '#overview';
        }, 400);
    } catch (err) {
        clearInterval(progressInterval);
        showSection('upload-section');
        const errEl = document.getElementById('upload-error');
        errEl.textContent = 'Analysis failed: ' + err.message;
        errEl.style.display = '';
    }
}

// ---- Tab Routing ----
(function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            window.location.hash = '#' + btn.dataset.tab;
        });
    });
    window.addEventListener('hashchange', applyHash);
    // Apply on load if results are visible
    if (window.location.hash) applyHash();
})();

function applyHash() {
    const hash = window.location.hash.replace('#', '') || 'overview';
    document.querySelectorAll('.tab-btn').forEach(btn => {
        const isActive = btn.dataset.tab === hash;
        btn.classList.toggle('active', isActive);
        // Update nav styling
        if (isActive) {
            btn.classList.add('text-stone-950', 'border-b-2', 'border-secondary', 'pb-1');
            btn.classList.remove('text-stone-600');
        } else {
            btn.classList.remove('text-stone-950', 'border-b-2', 'border-secondary', 'pb-1');
            btn.classList.add('text-stone-600');
        }
    });
    document.querySelectorAll('.tab-content').forEach(tc => {
        tc.classList.toggle('active', tc.id === 'tab-' + hash);
    });
    window.scrollTo(0, 0);
}

// ---- Render All Results ----
function renderResults(data) {
    renderOverview(data);
    renderHealth(data.health_risks || []);
    renderPharma(data.pharmacogenomics || []);
    renderTraits(data.traits || []);
    renderAncestry(data);
    initSearchAndFilters();
}

// ---- Overview Tab ----
function renderOverview(data) {
    const summary = data.summary || {};
    const critCount = summary.critical_alerts || summary.critical_count || 0;
    const highCount = summary.high_risk || summary.high_count || 0;
    const drugCount = summary.drug_interactions || summary.drug_interactions_count || 0;
    const traitCount = summary.traits_found || summary.traits_count || 0;

    document.getElementById('stat-critical').textContent = critCount;
    document.getElementById('stat-high').textContent = highCount;
    document.getElementById('stat-drugs').textContent = drugCount;
    document.getElementById('stat-traits').textContent = traitCount;
    document.getElementById('stat-total-variants').textContent = (summary.total_variants || summary.total_snps || 0).toLocaleString();
    document.getElementById('stat-matched-variants').textContent = (summary.matched_variants || summary.health_findings_count || 0).toLocaleString();
    document.getElementById('stat-health-findings').textContent = (summary.health_findings || summary.health_findings_count || summary.health_risks || 0).toLocaleString();

    // Bento grid display stats
    const critDisplay = document.getElementById('stat-critical-display');
    if (critDisplay) critDisplay.textContent = String(critCount).padStart(2, '0');
    const highDisplay = document.getElementById('stat-high-display');
    if (highDisplay) highDisplay.textContent = String(highCount).padStart(2, '0');
    const modEl = document.getElementById('stat-moderate');
    if (modEl) modEl.textContent = 0; // will be updated after severity count

    // Health findings summary text
    const hfSummary = document.getElementById('health-findings-summary');
    if (hfSummary) {
        const total = (data.health_risks || []).length;
        const pharmaCount = (data.pharmacogenomics || []).length;
        hfSummary.textContent = total > 0
            ? `Your DNA analysis identified ${total} health-related variants and ${pharmaCount} pharmacogenomic markers across ${(summary.total_variants || summary.total_snps || 0).toLocaleString()} analyzed SNPs.`
            : 'No significant health variants were identified in your genomic data.';
    }

    // Severity counts
    const sevCounts = {};
    (data.health_risks || []).forEach(r => {
        const s = (r.severity || '').toUpperCase();
        sevCounts[s] = (sevCounts[s] || 0) + 1;
    });
    DNACharts.createSeverityDonut('chart-severity-donut', sevCounts);

    // Update moderate count in donut legend
    const modEl2 = document.getElementById('stat-moderate');
    if (modEl2) modEl2.textContent = sevCounts['MODERATE'] || 0;

    // Critical alerts
    const criticals = (data.health_risks || []).filter(r => (r.severity || '').toUpperCase() === 'CRITICAL');
    const critPanel = document.getElementById('critical-alerts-panel');
    const critList = document.getElementById('critical-alerts-list');
    if (criticals.length > 0) {
        critPanel.style.display = '';
        critList.innerHTML = criticals.map(r => `
            <div class="critical-alert-card">
                <h4>${esc(r.gene || 'Unknown Gene')} — ${esc(r.condition || '')}</h4>
                <p>${esc(r.risk_description || r.description || '')}</p>
            </div>
        `).join('');
    } else {
        critPanel.style.display = 'none';
    }

    // Pharma preview (top 3 findings)
    const pharmaPreview = document.getElementById('overview-pharma-preview');
    if (pharmaPreview) {
        const pharma = data.pharmacogenomics || [];
        const top3 = pharma.slice(0, 3);
        if (top3.length > 0) {
            pharmaPreview.innerHTML = top3.map(p => {
                const status = (p.metabolizer_status || 'Normal').toLowerCase();
                let dotColor = 'bg-stone-500';
                if (status.includes('poor')) dotColor = 'bg-error';
                else if (status.includes('intermediate')) dotColor = 'bg-secondary';
                else if (status.includes('rapid') || status.includes('ultra')) dotColor = 'bg-secondary-container';
                const meds = (p.drugs_affected || []).slice(0, 2).map(m => typeof m === 'string' ? m : (m.drug || m.name || '')).join(', ');
                return `
                    <div class="flex items-center justify-between p-3 bg-white/20 rounded-lg border border-white/30">
                        <div class="flex items-center gap-3">
                            <span class="w-2 h-2 rounded-full ${dotColor} shrink-0"></span>
                            <span class="text-sm font-bold text-stone-950">${esc(p.gene || '')}</span>
                        </div>
                        <span class="text-xs text-stone-600 font-medium">${esc(p.metabolizer_status || '')}</span>
                    </div>`;
            }).join('');
        }
    }

    // Traits preview (top 4 results)
    const traitsPreview = document.getElementById('overview-traits-preview');
    if (traitsPreview) {
        const traits = data.traits || [];
        const top4 = traits.slice(0, 4);
        if (top4.length > 0) {
            traitsPreview.innerHTML = top4.map(t => {
                const catIcons = { nutrition: 'restaurant', physical: 'fitness_center', athletic: 'sports_score', sleep: 'bedtime', behavioral: 'psychology', other: 'science' };
                const cat = (t.category || 'other').toLowerCase();
                const icon = catIcons[cat] || 'science';
                return `
                    <div class="glass-panel p-4 rounded-lg">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="material-symbols-outlined text-sm text-secondary/70">${icon}</span>
                            <span class="text-xs font-bold text-primary truncate">${esc(t.name || t.trait || '')}</span>
                        </div>
                        <div class="text-lg font-extrabold text-primary leading-tight">${esc(t.result || t.value || '—')}</div>
                    </div>`;
            }).join('');
        }
    }
}

// ---- Health Risks Tab ----
function renderHealth(risks) {
    const container = document.getElementById('health-results');
    const emptyEl = document.getElementById('health-empty');
    if (!risks.length) {
        container.innerHTML = '';
        emptyEl.style.display = '';
        return;
    }
    emptyEl.style.display = 'none';

    // Sort: CRITICAL first
    const order = { CRITICAL: 0, HIGH: 1, MODERATE: 2, LOW: 3, PROTECTIVE: 4 };
    risks.sort((a, b) => (order[(a.severity||'').toUpperCase()] ?? 5) - (order[(b.severity||'').toUpperCase()] ?? 5));

    container.innerHTML = risks.map((r, i) => {
        const sev = (r.severity || 'LOW').toUpperCase();
        const details = r.details || {};
        const recs = details.recommendations || r.recommendations || [];
        const stars = details.clinvar_stars != null ? details.clinvar_stars : (r.clinvar_stars != null ? r.clinvar_stars : null);
        const popFreq = details.population_frequency || r.population_frequency;
        const oddsRatio = details.odds_ratio || r.odds_ratio;
        const explanation = details.explanation || r.explanation || '';

        const whatThisMeans = r.what_this_means || '';
        const inheritance = r.inheritance || '';
        const category = r.category || '';
        const absRisk = r.absolute_risk || '';

        // Severity styling maps
        let iconName, iconBgClass, badgeClass, borderClass;
        switch (sev) {
            case 'CRITICAL':
                iconName = 'warning';
                iconBgClass = 'bg-error-container/95 text-on-error-container';
                badgeClass = 'bg-error text-white text-[10px] px-2 py-0.5 rounded-full font-black uppercase tracking-widest shadow-sm';
                borderClass = 'border-l-4 border-l-error';
                break;
            case 'HIGH':
                iconName = 'health_metrics';
                iconBgClass = 'bg-amber-100 text-amber-800';
                badgeClass = 'bg-amber-600 text-white text-[10px] px-2 py-0.5 rounded-full font-black uppercase tracking-widest shadow-sm';
                borderClass = '';
                break;
            case 'MODERATE':
                iconName = 'ecg_heart';
                iconBgClass = 'bg-sky-100 text-sky-800';
                badgeClass = 'bg-secondary text-white text-[10px] px-2 py-0.5 rounded-full font-black uppercase tracking-widest shadow-sm';
                borderClass = '';
                break;
            case 'PROTECTIVE':
                iconName = 'shield_with_heart';
                iconBgClass = 'bg-emerald-100 text-emerald-800';
                badgeClass = 'bg-emerald-600 text-white text-[10px] px-2 py-0.5 rounded-full font-black uppercase tracking-widest shadow-sm';
                borderClass = 'border-l-4 border-l-emerald-500';
                break;
            default: // LOW
                iconName = 'monitoring';
                iconBgClass = 'bg-stone-100 text-stone-600';
                badgeClass = 'bg-stone-500 text-white text-[10px] px-2 py-0.5 rounded-full font-black uppercase tracking-widest shadow-sm';
                borderClass = '';
                break;
        }

        const searchText = esc((r.gene||'') + ' ' + (r.condition||'') + ' ' + (r.rsid||'')).toLowerCase();

        return `
        <article class="group glass-item p-6 rounded-xl hover:bg-white/30 transition-all flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6 ${borderClass} result-card" data-severity="${sev}" data-search="${searchText}" onclick="toggleCard(this)">
            <div class="flex flex-col md:flex-row gap-6 md:items-center flex-1">
                <div class="w-14 h-14 ${iconBgClass} rounded-lg flex items-center justify-center shrink-0 shadow-md">
                    <span class="material-symbols-outlined text-3xl" style='font-variation-settings: "FILL" 1'>${iconName}</span>
                </div>
                <div>
                    <div class="flex items-center gap-3 mb-1">
                        <h3 class="text-xl font-bold tracking-tight text-stone-950">${esc(r.gene || 'Unknown')} — ${esc(r.condition || '')}</h3>
                        <span class="${badgeClass}">${sev}</span>
                    </div>
                    <p class="text-stone-700 font-medium max-w-lg leading-snug text-sm">${esc(r.risk_description || r.description || '')}</p>
                </div>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-6 lg:gap-10 shrink-0">
                <div class="flex flex-col"><span class="text-[10px] text-stone-600 font-bold uppercase tracking-wider mb-1">Gene</span><span class="font-mono text-sm font-bold data-chip">${esc(r.gene || '—')}</span></div>
                <div class="flex flex-col"><span class="text-[10px] text-stone-600 font-bold uppercase tracking-wider mb-1">rsid</span><span class="font-mono text-sm text-secondary font-bold data-chip">${esc(r.rsid || '—')}</span></div>
                <div class="flex flex-col"><span class="text-[10px] text-stone-600 font-bold uppercase tracking-wider mb-1">Genotype</span><span class="font-bold text-sm data-chip">${esc(r.your_genotype || r.genotype || '—')}</span></div>
                <div class="flex flex-col"><span class="text-[10px] text-stone-600 font-bold uppercase tracking-wider mb-1">Zygosity</span><span class="text-sm font-bold data-chip">${esc(r.zygosity || '—')}</span></div>
            </div>
            <span class="material-symbols-outlined text-stone-400 group-hover:translate-x-1 group-hover:text-stone-950 transition-all cursor-pointer expand-icon">chevron_right</span>
            <!-- Expanded body (hidden by default) -->
            <div class="result-card-body w-full">
                ${whatThisMeans ? `
                    <div class="health-section">
                        <div class="health-section-label">What this means for you</div>
                        <p>${escPlain(whatThisMeans)}</p>
                    </div>` : ''}
                ${r.risk_description ? `
                    <div class="health-section">
                        <div class="health-section-label">About this variant</div>
                        <p>${escPlain(r.risk_description)}</p>
                    </div>` : ''}
                <div class="health-section">
                    <div class="health-section-label">Your result</div>
                    <p>Your genotype is <strong>${esc(r.your_genotype || '')}</strong>
                    (you carry ${r.zygosity === 'homozygous' ? 'two copies' : 'one copy'} of this variant).
                    ${inheritance ? ` Inheritance: ${escPlain(inheritance)}.` : ''}
                    ${absRisk && absRisk !== '0.00%' && absRisk !== '1.00%' ? ` Based on population data, the estimated lifetime risk is about ${esc(absRisk)}.` : ''}</p>
                </div>
                <div class="result-detail-grid" style="margin-top:12px">
                    ${popFreq != null ? `
                        <div class="detail-item">
                            <div class="detail-label">How common is this variant?</div>
                            <div class="detail-value">${(popFreq * 100).toFixed(1)}% of people carry it</div>
                            <div class="population-freq-bar"><div class="population-freq-fill" style="width:${Math.min(100, popFreq * 100)}%"></div></div>
                        </div>` : ''}
                    ${oddsRatio != null && oddsRatio > 1 ? `<div class="detail-item"><div class="detail-label">Risk multiplier</div><div class="detail-value">${oddsRatio}x compared to average</div></div>` : ''}
                    ${stars != null ? `<div class="detail-item"><div class="detail-label">Evidence quality</div><div class="detail-value"><span class="clinvar-stars">${'★'.repeat(stars)}${'☆'.repeat(Math.max(0, 4 - stars))}</span></div></div>` : ''}
                </div>
                <div class="health-section health-next-steps">
                    <div class="health-section-label">What to do</div>
                    <p>${sev === 'CRITICAL' || sev === 'HIGH'
                        ? 'Consider discussing this result with your doctor or a genetic counselor. They can order confirmatory testing and advise on any precautions.'
                        : sev === 'PROTECTIVE'
                        ? 'This is a positive finding — no action needed.'
                        : 'This is worth being aware of. Mention it at your next doctor visit if relevant to your health history.'}</p>
                </div>
            </div>
        </article>`;
    }).join('');
}

// ---- Pharmacogenomics Tab ----
function renderPharma(pharma) {
    const container = document.getElementById('pharma-results');
    const emptyEl = document.getElementById('pharma-empty');
    if (!pharma.length) {
        container.innerHTML = '';
        emptyEl.style.display = '';
        return;
    }
    emptyEl.style.display = 'none';

    // Show critical drug interactions panel
    const criticals = pharma.filter(p => p.is_critical);
    const critPanel = document.getElementById('pharma-critical-panel');
    const critList = document.getElementById('pharma-critical-list');
    if (criticals.length > 0) {
        critPanel.style.display = '';
        critList.innerHTML = criticals.map(p => {
            const meds = (p.drugs_affected || []).slice(0, 3).map(m => typeof m === 'string' ? m : (m.drug || m.name || '')).join(', ');
            return `
            <div class="group flex items-start gap-6 p-6 bg-white/20 hover:bg-white/40 transition-all rounded-xl border border-white/40 shadow-sm mb-4">
                <div class="p-4 bg-error text-white rounded-xl shadow-lg shrink-0">
                    <span class="material-symbols-outlined">medication</span>
                </div>
                <div class="flex-grow">
                    <div class="flex justify-between items-baseline mb-2">
                        <h3 class="text-xl font-extrabold tracking-tight text-stone-950">${esc(p.gene || '')} <span class="text-stone-500 font-medium text-sm ml-1">${esc(p.metabolizer_status || '')}</span></h3>
                        <span class="text-xs font-black tracking-widest text-stone-600 bg-white/50 px-2 py-0.5 rounded">${esc(p.gene || '')}</span>
                    </div>
                    <p class="text-sm text-stone-800 font-medium leading-relaxed mb-4">${esc(p.description || '')}</p>
                    <div class="flex gap-2 flex-wrap">
                        <span class="px-3 py-1 bg-stone-950 text-white text-[9px] font-black uppercase tracking-widest rounded-lg">Action Required</span>
                        ${meds ? `<span class="px-3 py-1 bg-white/60 border border-stone-300 text-[9px] font-black uppercase tracking-widest rounded-lg text-stone-700">${esc(meds)}</span>` : ''}
                    </div>
                </div>
            </div>`;
        }).join('');
    } else {
        critPanel.style.display = 'none';
    }

    // Build drug-category index from all pharma data
    const categoryMap = {};
    const categoryIcons = {
        'cardiovascular': 'cardiology', 'hypertension': 'cardiology', 'coronary': 'cardiology',
        'mental health': 'psychology', 'depressive': 'psychology', 'schizophrenia': 'psychology',
        'oncology': 'biotech', 'neoplasm': 'biotech', 'carcinoma': 'biotech', 'cancer': 'biotech', 'osteosarcoma': 'biotech',
        'pain': 'medication', 'opioid': 'medication', 'heroin': 'medication',
        'immune': 'immunology', 'arthritis': 'immunology', 'psoriasis': 'immunology', 'asthma': 'immunology',
        'infectious': 'coronavirus', 'hiv': 'coronavirus',
    };

    pharma.forEach(p => {
        (p.drugs_affected || []).forEach(d => {
            const drug = typeof d === 'string' ? { drug: d } : d;
            const rawCats = (drug.category || '').split(';').map(c => c.trim()).filter(Boolean);
            if (!rawCats.length) rawCats.push('Other');
            // Normalize into broader categories
            rawCats.forEach(rc => {
                let bucket = rc;
                const rcl = rc.toLowerCase();
                if (rcl.includes('depress') || rcl.includes('schizophreni') || rcl.includes('bipolar') || rcl.includes('anxiety')) bucket = 'Mental Health';
                else if (rcl.includes('hypertens') || rcl.includes('coronary') || rcl.includes('cardiac') || rcl.includes('heart') || rcl.includes('atrial')) bucket = 'Cardiovascular';
                else if (rcl.includes('neoplas') || rcl.includes('carcinom') || rcl.includes('cancer') || rcl.includes('sarcoma') || rcl.includes('leukemia') || rcl.includes('lymphoma') || rcl.includes('tumor')) bucket = 'Oncology';
                else if (rcl.includes('opioid') || rcl.includes('heroin') || rcl.includes('pain') || rcl.includes('analges')) bucket = 'Pain & Addiction';
                else if (rcl.includes('arthritis') || rcl.includes('psoriasis') || rcl.includes('asthma') || rcl.includes('autoimmun') || rcl.includes('lupus') || rcl.includes('inflammat')) bucket = 'Immune & Inflammatory';
                else if (rcl.includes('hiv') || rcl.includes('hepat') || rcl.includes('tuberc') || rcl.includes('infect')) bucket = 'Infectious Disease';
                else if (rcl.includes('diabet') || rcl.includes('cholesterol') || rcl.includes('obesity') || rcl.includes('lipid')) bucket = 'Metabolic';
                else if (rcl.includes('stroke') || rcl.includes('epilep') || rcl.includes('seizure') || rcl.includes('neuro') || rcl.includes('alzheimer')) bucket = 'Neurological';

                if (!categoryMap[bucket]) categoryMap[bucket] = [];
                categoryMap[bucket].push({
                    gene: p.gene,
                    drug: drug.drug || drug.name || '',
                    guidance: (drug.guidance || '').substring(0, 150),
                    category: rc,
                    status: p.metabolizer_status
                });
            });
        });
    });

    // Sort categories by count, deduplicate entries within each
    const sortedCats = Object.entries(categoryMap)
        .map(([name, items]) => {
            // Deduplicate by gene+drug
            const seen = new Set();
            const unique = items.filter(i => {
                const key = i.gene + '|' + i.drug;
                if (seen.has(key)) return false;
                seen.add(key);
                return true;
            });
            return [name, unique];
        })
        .sort((a, b) => b[1].length - a[1].length);

    // Build category pill filters + drug cards
    const ITEMS_PER_CAT = 6;

    // Populate sidebar with category summary
    const sidebarContainer = document.getElementById('medication-sensitivity');
    if (sidebarContainer) {
        const innerDiv = sidebarContainer.querySelector('.space-y-4, .space-y-8') || sidebarContainer.lastElementChild;
        if (innerDiv) {
            innerDiv.innerHTML = sortedCats.map(([catName, items]) => {
                const icon = Object.entries(categoryIcons).find(([k]) => catName.toLowerCase().includes(k));
                return `
                <div class="flex items-center justify-between p-3 bg-white/40 rounded-lg border border-white/60 hover:bg-white/60 transition-colors cursor-pointer"
                     onclick="filterPharmaByCategory('${esc(catName)}')">
                    <div class="flex items-center gap-3">
                        <span class="material-symbols-outlined text-secondary/70 text-lg">${icon ? icon[1] : 'science'}</span>
                        <span class="text-sm font-bold text-stone-950">${esc(catName)}</span>
                    </div>
                    <span class="text-xs font-bold text-stone-500 bg-white/50 px-2 py-0.5 rounded-full">${items.length}</span>
                </div>`;
            }).join('');
        }
    }

    // Render main results as category groups
    container.innerHTML = sortedCats.map(([catName, items]) => {
        const shown = items.slice(0, ITEMS_PER_CAT);
        const remaining = items.length - shown.length;
        const icon = Object.entries(categoryIcons).find(([k]) => catName.toLowerCase().includes(k));
        return `
        <div class="pharma-category-group mb-8" data-pharma-category="${esc(catName)}">
            <div class="flex items-center gap-3 mb-4">
                <span class="material-symbols-outlined text-secondary/70">${icon ? icon[1] : 'science'}</span>
                <h3 class="text-lg font-extrabold tracking-tight text-stone-950">${esc(catName)}</h3>
                <span class="text-xs font-bold text-stone-400">${items.length} interactions</span>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                ${shown.map(item => `
                <div class="pharma-card glass-item p-4 rounded-xl hover:bg-white/40 transition-all cursor-pointer" data-search="${esc((item.gene + ' ' + item.drug + ' ' + catName).toLowerCase())}" onclick="toggleCard(this)">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-sm font-extrabold text-stone-950">${esc(item.gene)}</span>
                        <span class="text-[10px] font-bold text-stone-500 bg-white/50 px-2 py-0.5 rounded uppercase tracking-wider">${esc(item.status || '')}</span>
                    </div>
                    <div class="text-sm font-semibold text-secondary mb-1">${esc(item.drug)}</div>
                    <div class="pharma-card-body">
                        <p class="text-xs text-stone-600 leading-relaxed mt-2 pt-2 border-t border-white/40">${esc(item.guidance)}${item.guidance.length >= 150 ? '...' : ''}</p>
                    </div>
                </div>`).join('')}
            </div>
            ${remaining > 0 ? `
            <button class="mt-3 text-xs font-bold text-secondary hover:underline uppercase tracking-widest flex items-center gap-1"
                    onclick="expandPharmaCategory(this, '${esc(catName)}')">
                Show ${remaining} more <span class="material-symbols-outlined text-sm">expand_more</span>
            </button>` : ''}
        </div>`;
    }).join('');

    // Store full data for expand functionality
    window._pharmaCategoryData = Object.fromEntries(sortedCats);

    // Render metabolism insight
    renderMetabolismInsight(pharma);
}

function renderMetabolismInsight(pharma) {
    const container = document.getElementById('metabolism-insight');
    if (!container) return;

    const counts = { poor: 0, intermediate: 0, normal: 0, rapid: 0 };
    pharma.forEach(p => {
        const status = (p.metabolizer_status || 'Normal').toLowerCase();
        if (status.includes('poor')) counts.poor++;
        else if (status.includes('intermediate')) counts.intermediate++;
        else if (status.includes('rapid') || status.includes('ultra')) counts.rapid++;
        else counts.normal++;
    });

    const total = pharma.length || 1;
    const pctPoor = Math.round(counts.poor / total * 100);
    const pctIntermediate = Math.round(counts.intermediate / total * 100);
    const pctNormal = Math.round(counts.normal / total * 100);
    const pctRapid = Math.round(counts.rapid / total * 100);

    const bars = [
        { label: 'Poor Metabolizer', pct: pctPoor, color: 'bg-error' },
        { label: 'Intermediate', pct: pctIntermediate, color: 'bg-secondary' },
        { label: 'Normal', pct: pctNormal, color: 'bg-stone-950' },
        { label: 'Rapid', pct: pctRapid, color: 'bg-secondary-container' },
    ];

    container.innerHTML = `
        <h3 class="font-extrabold text-stone-950 mb-6 flex items-center gap-2 uppercase text-xs tracking-[0.2em]">
            <span class="material-symbols-outlined text-sm">monitoring</span> Metabolism Insight
        </h3>
        <div class="space-y-5">
            ${bars.map(b => `
                <div>
                    <div class="flex justify-between text-[10px] font-black uppercase text-stone-600 mb-2 tracking-widest">
                        <span>${b.label}</span>
                        <span class="text-stone-950">${b.pct}%</span>
                    </div>
                    <div class="h-1.5 w-full bg-stone-200/50 rounded-full overflow-hidden">
                        <div class="h-full ${b.color} rounded-full" style="width:${b.pct}%"></div>
                    </div>
                </div>
            `).join('')}
        </div>`;
}

// ---- Pharma category helpers ----
function filterPharmaByCategory(catName) {
    const groups = document.querySelectorAll('.pharma-category-group');
    groups.forEach(g => {
        if (catName === 'all') {
            g.style.display = '';
        } else {
            g.style.display = g.dataset.pharmaCategory === catName ? '' : 'none';
        }
    });
}

function expandPharmaCategory(btn, catName) {
    const data = window._pharmaCategoryData?.[catName] || [];
    const group = btn.closest('.pharma-category-group');
    const grid = group?.querySelector('.grid');
    if (!grid) return;
    // Render all remaining items
    const existing = grid.children.length;
    const remaining = data.slice(existing);
    remaining.forEach(item => {
        const div = document.createElement('div');
        div.className = 'pharma-card glass-item p-4 rounded-xl hover:bg-white/40 transition-all cursor-pointer';
        div.dataset.search = (item.gene + ' ' + item.drug + ' ' + catName).toLowerCase();
        div.onclick = function() { toggleCard(this); };
        div.innerHTML = `
            <div class="flex items-center justify-between mb-2">
                <span class="text-sm font-extrabold text-stone-950">${esc(item.gene)}</span>
                <span class="text-[10px] font-bold text-stone-500 bg-white/50 px-2 py-0.5 rounded uppercase tracking-wider">${esc(item.status || '')}</span>
            </div>
            <div class="text-sm font-semibold text-secondary mb-1">${esc(item.drug)}</div>
            <div class="pharma-card-body">
                <p class="text-xs text-stone-600 leading-relaxed mt-2 pt-2 border-t border-white/40">${esc(item.guidance)}${item.guidance.length >= 150 ? '...' : ''}</p>
            </div>`;
        grid.appendChild(div);
    });
    btn.remove();
}

// ---- Traits Tab ----
function renderTraits(traits) {
    const container = document.getElementById('traits-results');
    const emptyEl = document.getElementById('traits-empty');
    if (!traits.length) {
        container.innerHTML = '';
        emptyEl.style.display = '';
        return;
    }
    emptyEl.style.display = 'none';

    const catIcons = { nutrition: 'restaurant', physical: 'fitness_center', athletic: 'sports_score', sleep: 'bedtime', behavioral: 'psychology', other: 'science' };

    container.innerHTML = traits.map(t => {
        const cat = (t.category || 'other').toLowerCase();
        const conf = (t.confidence || 'medium').toLowerCase();
        const popFreq = t.population_frequency;
        const icon = catIcons[cat] || 'science';

        let confBadgeClass;
        switch (conf) {
            case 'high':
                confBadgeClass = 'bg-emerald-100 text-emerald-800 text-[10px] px-2 py-0.5 rounded-full font-black uppercase tracking-widest';
                break;
            case 'low':
                confBadgeClass = 'bg-stone-100 text-stone-500 text-[10px] px-2 py-0.5 rounded-full font-black uppercase tracking-widest';
                break;
            default:
                confBadgeClass = 'bg-secondary/10 text-secondary text-[10px] px-2 py-0.5 rounded-full font-black uppercase tracking-widest';
                break;
        }

        const freqPct = popFreq != null ? Math.min(100, Math.max(0, popFreq * 100)).toFixed(0) : null;

        return `
        <div class="glass-panel p-6 rounded-xl hover:shadow-xl transition-all group trait-card" data-category="${esc(cat)}">
            <div class="flex justify-between items-start mb-4">
                <span class="material-symbols-outlined text-2xl text-secondary/70">${icon}</span>
                <span class="${confBadgeClass}">${conf}</span>
            </div>
            <h3 class="font-bold text-lg tracking-tight text-primary mb-1">${esc(t.name || t.trait || '')}</h3>
            <div class="text-2xl font-extrabold text-primary mb-3">${esc(t.result || t.value || '—')}</div>
            <p class="text-sm text-on-surface-variant leading-relaxed mb-4">${esc(t.explanation || t.description || '')}</p>
            ${freqPct !== null ? `
            <div class="flex items-center gap-2 text-[10px] uppercase tracking-wider text-stone-500">
                <span>Pop. frequency:</span>
                <div class="flex-1 h-1.5 bg-stone-200/50 rounded-full overflow-hidden max-w-[100px]"><div class="h-full bg-primary/60 rounded-full" style="width:${freqPct}%"></div></div>
                <span class="font-bold">${freqPct}%</span>
            </div>` : ''}
        </div>`;
    }).join('');

    // Category sub-tab click handlers
    document.querySelectorAll('.category-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.category-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filterTraits(btn.dataset.category);
        });
    });
}

function filterTraits(category) {
    const cards = document.querySelectorAll('#traits-results .trait-card');
    let visible = 0;
    cards.forEach(card => {
        const show = category === 'all' || card.dataset.category === category;
        card.style.display = show ? '' : 'none';
        if (show) visible++;
    });
    document.getElementById('traits-empty').style.display = visible ? 'none' : '';
}

// ---- Ancestry Tab ----
function renderAncestry(data) {
    const ancestry = data.ancestry || {};
    // Maternal haplogroup
    const mhg = ancestry.maternal_haplogroup || {};
    const mhgName = mhg.name || mhg.haplogroup || '—';
    document.getElementById('maternal-hg-name').textContent = mhgName;
    document.getElementById('maternal-hg-desc').textContent = mhg.description || mhg.geographic_description || '';
    if (mhgName === 'Not available' || mhgName === 'Unknown') {
        document.getElementById('maternal-hg-name').style.color = 'rgba(11,16,18,0.35)';
    }

    // Paternal haplogroup
    const phg = ancestry.paternal_haplogroup || {};
    document.getElementById('paternal-hg-name').textContent = phg.name || phg.haplogroup || '—';
    document.getElementById('paternal-hg-desc').textContent = phg.description || phg.geographic_description || '';
    // Hide paternal if not available (e.g. female sample)
    document.getElementById('paternal-haplogroup').style.display = (phg.name || phg.haplogroup) ? '' : 'none';

    // Ancestry composition — render as horizontal progress bars in a dark panel
    const comp = ancestry.composition || [];
    const compSection = document.getElementById('ancestry-composition-section');
    if (comp.length > 0) {
        compSection.style.display = '';

        // Replace the canvas-based bar chart with glass-panel-dark progress bars
        const chartWrapper = compSection.querySelector('.chart-wrapper');
        if (chartWrapper) {
            const regionColors = [
                '#4a6fa5', '#7a5ca8', '#3d8b63', '#9e8230', '#c0392b',
                '#a05a8a', '#3a8e9e', '#6a8e4a', '#b8652e', '#5a5aa8',
            ];
            chartWrapper.className = 'glass-panel p-8 rounded-2xl';
            chartWrapper.style.background = 'rgba(30,30,30,0.85)';
            chartWrapper.style.backdropFilter = 'blur(40px)';
            chartWrapper.innerHTML = `
                <div class="space-y-4">
                    ${comp.map((c, i) => {
                        const region = c.region || c.population || c.name || '';
                        const pct = c.percentage || 0;
                        const color = regionColors[i % regionColors.length];
                        return `
                        <div>
                            <div class="flex justify-between text-[10px] font-black uppercase text-stone-300 mb-2 tracking-widest">
                                <span>${esc(region)}</span>
                                <span class="text-white">${pct.toFixed(1)}%</span>
                            </div>
                            <div class="h-2 w-full bg-white/10 rounded-full overflow-hidden">
                                <div class="h-full rounded-full transition-all" style="width:${pct}%;background:${color}"></div>
                            </div>
                        </div>`;
                    }).join('')}
                </div>`;
        }

        // Render world map if container exists
        const mapContainer = document.getElementById('ancestry-world-map');
        if (mapContainer) {
            DNACharts.createWorldMap('ancestry-world-map', comp);
        }
    } else {
        compSection.style.display = 'none';
    }

    // PRS — render as SVG gauges
    const prs = data.polygenic_risk || [];
    const prsSection = document.getElementById('prs-section');
    const prsGrid = document.getElementById('prs-grid');
    if (prs.length > 0) {
        prsSection.style.display = '';
        prsGrid.innerHTML = '';
        prs.forEach(p => {
            const card = document.createElement('div');
            card.className = 'prs-card';
            card.innerHTML = `
                <div class="prs-card-condition">${esc(p.condition || p.trait || '')}</div>
                <div class="prs-gauge-wrapper" id="prs-gauge-${esc(p.condition || '')}"></div>
            `;
            prsGrid.appendChild(card);
            const gaugeContainer = card.querySelector('.prs-gauge-wrapper');
            DNACharts.createPRSGaugeSVG(gaugeContainer, p.percentile || 0, p.condition || '');
        });
    } else {
        prsSection.style.display = 'none';
    }

    // Coverage
    const coverage = ancestry.coverage || [];
    const covSection = document.getElementById('coverage-section');
    const covContainer = document.getElementById('coverage-indicators');
    if (coverage.length > 0) {
        covSection.style.display = '';
        covContainer.innerHTML = coverage.map(c => {
            const level = (c.level || 'good').toLowerCase();
            return `
                <div class="coverage-item">
                    <span class="coverage-dot coverage-${level}"></span>
                    <span>${esc(c.label || c.name || '')} — ${esc(c.description || level)}</span>
                </div>
            `;
        }).join('');
    } else {
        covSection.style.display = 'none';
    }
}

// ---- Search & Filter ----
function initSearchAndFilters() {
    // Health search
    const healthSearch = document.getElementById('health-search');
    const healthFilter = document.getElementById('health-severity-filter');
    if (healthSearch) {
        healthSearch.addEventListener('input', () => filterHealth());
    }
    if (healthFilter) {
        healthFilter.addEventListener('change', () => filterHealth());
    }

    // Pharma search
    const pharmaSearch = document.getElementById('pharma-search');
    if (pharmaSearch) {
        pharmaSearch.addEventListener('input', () => filterPharma());
    }
}

function filterHealth() {
    const query = (document.getElementById('health-search').value || '').toLowerCase();
    const severity = document.getElementById('health-severity-filter').value;
    const cards = document.querySelectorAll('#health-results .result-card');
    let visible = 0;

    cards.forEach(card => {
        const matchSearch = !query || (card.dataset.search || '').includes(query);
        const matchSev = severity === 'all' || card.dataset.severity === severity;
        const show = matchSearch && matchSev;
        card.style.display = show ? '' : 'none';
        if (show) visible++;
    });

    document.getElementById('health-empty').style.display = visible ? 'none' : '';
}

function filterPharma() {
    const query = (document.getElementById('pharma-search').value || '').toLowerCase();
    const cards = document.querySelectorAll('#pharma-results .pharma-card');
    let visible = 0;

    cards.forEach(card => {
        const show = !query || (card.dataset.search || '').includes(query);
        card.style.display = show ? '' : 'none';
        if (show) visible++;
    });

    document.getElementById('pharma-empty').style.display = visible ? 'none' : '';
}

// ---- Card Expand/Collapse ----
function toggleCard(card) {
    card.classList.toggle('expanded');
}

// ---- Plain-English Translation ----
const JARGON = {
    'hemolytic anemia': 'a condition where red blood cells break down faster than normal, causing fatigue, pale skin, and sometimes yellowing of the eyes',
    'hemolytic crises': 'episodes where many red blood cells suddenly break down, causing severe fatigue, dark urine, and yellowing skin — can require emergency care',
    'hemizygous': 'having one copy of the gene (on the X chromosome)',
    'homozygous': 'carrying two copies of this variant (one from each parent)',
    'heterozygous': 'carrying one copy of this variant (from one parent)',
    'heterozygote': 'a person carrying one copy of this variant',
    'pathogenic': 'known to cause disease',
    'autosomal recessive': 'both parents must pass on the variant for the condition to develop',
    'autosomal dominant': 'only one copy of the variant is needed for the condition to develop',
    'x-linked': 'carried on the X chromosome — affects males more severely since they only have one X',
    'oxidative stressors': 'things that put stress on your body like infections, certain foods (fava beans), and certain medications',
    'thrombophilia': 'an increased tendency for blood clots to form',
    'venous thromboembolism': 'blood clots forming in veins, which can travel to the lungs (pulmonary embolism)',
    'hypercholesterolemia': 'very high cholesterol levels',
    'hypertriglyceridemia': 'high levels of triglycerides (a type of fat) in the blood',
    'homocysteinemia': 'elevated levels of homocysteine in the blood, which may increase heart disease risk',
    'macular degeneration': 'gradual loss of central vision, making it harder to read, drive, or see faces clearly',
    'atrial fibrillation': 'an irregular and often rapid heart rhythm that can cause palpitations, shortness of breath, and fatigue',
    'myocardial infarction': 'heart attack',
    'neural tube defect': 'a birth defect of the brain or spine that develops in early pregnancy',
    'sulfonamides': 'a class of antibiotics (like Bactrim/Septra)',
    'primaquine': 'an anti-malaria medication',
    'dapsone': 'an antibiotic used for skin conditions and infections',
    'nitrofurantoin': 'an antibiotic commonly used for urinary tract infections (UTIs)',
    'penetrance': 'the likelihood that someone with this variant will actually develop the condition',
    'allele': 'a version of a gene',
    'enzyme activity': 'how well a specific protein in your body does its job',
    'melanin': 'the pigment that gives color to skin, hair, and eyes',
    'coronary artery disease': 'narrowing of the blood vessels that supply the heart, which can lead to chest pain or heart attacks',
    'statin-induced myopathy': 'muscle pain and weakness caused by cholesterol-lowering statin drugs',
    'alpha-1 antitrypsin deficiency': 'a condition that can damage the lungs and liver because the body does not make enough of a protective protein',
};

function plainEnglish(text) {
    if (!text) return '';
    let result = text;
    // Sort by length descending so longer phrases are replaced first
    const sorted = Object.entries(JARGON).sort((a, b) => b[0].length - a[0].length);
    for (const [term, explanation] of sorted) {
        const regex = new RegExp('\\b' + term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'gi');
        if (regex.test(result)) {
            result = result.replace(regex, match => `${match} (${explanation})`);
        }
    }
    return result;
}

// ---- Escape HTML ----
function esc(str) {
    if (str == null) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

// Escape then add plain-english glossary expansions
function escPlain(str) {
    return plainEnglish(esc(str));
}
