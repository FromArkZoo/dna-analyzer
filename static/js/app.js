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
        btn.classList.toggle('active', btn.dataset.tab === hash);
    });
    document.querySelectorAll('.tab-content').forEach(tc => {
        tc.classList.toggle('active', tc.id === 'tab-' + hash);
    });
}

// ---- Render All Results ----
function renderResults(data) {
    renderOverview(data);
    renderHealth(data.health_risks || []);
    renderPharma(data.pharmacogenomics || []);
    renderTraits(data.traits || []);
    renderAncestry(data.ancestry || {});
    initSearchAndFilters();
}

// ---- Overview Tab ----
function renderOverview(data) {
    const summary = data.summary || {};
    document.getElementById('stat-critical').textContent = summary.critical_alerts || summary.critical_count || 0;
    document.getElementById('stat-high').textContent = summary.high_risk || summary.high_count || 0;
    document.getElementById('stat-drugs').textContent = summary.drug_interactions || summary.drug_interactions_count || 0;
    document.getElementById('stat-traits').textContent = summary.traits_found || summary.traits_count || 0;
    document.getElementById('stat-total-variants').textContent = (summary.total_variants || summary.total_snps || 0).toLocaleString();
    document.getElementById('stat-matched-variants').textContent = (summary.matched_variants || summary.health_findings_count || 0).toLocaleString();
    document.getElementById('stat-health-findings').textContent = (summary.health_findings || summary.health_findings_count || summary.health_risks || 0).toLocaleString();

    // Severity counts
    const sevCounts = {};
    (data.health_risks || []).forEach(r => {
        const s = (r.severity || '').toUpperCase();
        sevCounts[s] = (sevCounts[s] || 0) + 1;
    });
    DNACharts.createSeverityDonut('chart-severity-donut', sevCounts);

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

        return `
        <div class="result-card" data-severity="${sev}" data-search="${esc((r.gene||'') + ' ' + (r.condition||'') + ' ' + (r.rsid||'')).toLowerCase()}" onclick="toggleCard(this)">
            <div class="result-card-header">
                <span class="severity-badge severity-${sev}">${sev}</span>
                <div class="result-card-info">
                    <div class="result-card-gene">${esc(r.gene || 'Unknown')}</div>
                    <div class="result-card-condition">${esc(r.condition || '')}</div>
                </div>
                ${r.rsid ? `<span class="result-card-rsid">${esc(r.rsid)}</span>` : ''}
                ${r.zygosity ? `<span class="zygosity-badge">${esc(r.zygosity)}</span>` : ''}
                <span class="expand-icon">&#9660;</span>
            </div>
            <div class="result-card-body">
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
        </div>`;
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
    const criticals = pharma.filter(p => p.critical);
    const critPanel = document.getElementById('pharma-critical-panel');
    const critList = document.getElementById('pharma-critical-list');
    if (criticals.length > 0) {
        critPanel.style.display = '';
        critList.innerHTML = criticals.map(p => `
            <div class="critical-alert-card">
                <h4>${esc(p.gene || '')} — ${esc(p.metabolizer_status || '')}</h4>
                <p>${esc(p.description || (p.medications || []).map(m => typeof m === 'string' ? m : m.name).join(', '))}</p>
            </div>
        `).join('');
    } else {
        critPanel.style.display = 'none';
    }

    container.innerHTML = pharma.map(p => {
        const status = (p.metabolizer_status || 'Normal').toLowerCase().replace(/\s+/g, '');
        let badgeClass = 'metabolizer-normal';
        if (status.includes('poor')) badgeClass = 'metabolizer-poor';
        else if (status.includes('intermediate')) badgeClass = 'metabolizer-intermediate';
        else if (status.includes('ultra')) badgeClass = 'metabolizer-ultrarapid';
        else if (status.includes('rapid')) badgeClass = 'metabolizer-rapid';

        const meds = p.medications || [];
        const medsTable = meds.length ? `
            <table class="medications-table">
                <thead><tr><th>Medication</th><th>Impact</th><th>Recommendation</th></tr></thead>
                <tbody>
                    ${meds.map(m => {
                        const med = typeof m === 'string' ? { name: m } : m;
                        const isCrit = med.critical || (p.critical && true);
                        return `<tr class="${isCrit ? 'med-critical' : ''}">
                            <td>${esc(med.name || med.drug || m)}</td>
                            <td>${esc(med.impact || med.effect || '—')}</td>
                            <td>${esc(med.recommendation || '—')}</td>
                        </tr>`;
                    }).join('')}
                </tbody>
            </table>` : '<p style="color:#9CA3AF;font-size:.85rem">No specific medications listed.</p>';

        const searchText = [p.gene, p.metabolizer_status, ...meds.map(m => typeof m === 'string' ? m : (m.name || m.drug || ''))].join(' ').toLowerCase();

        return `
        <div class="pharma-card" data-search="${esc(searchText)}" onclick="toggleCard(this)">
            <div class="pharma-card-header">
                <span class="pharma-gene-name">${esc(p.gene || 'Unknown')}</span>
                <span class="metabolizer-badge ${badgeClass}">${esc(p.metabolizer_status || 'Unknown')}</span>
                <span class="expand-icon">&#9660;</span>
            </div>
            <div class="pharma-card-body">
                ${p.description ? `<p class="risk-description" style="margin-bottom:12px">${esc(p.description)}</p>` : ''}
                ${medsTable}
            </div>
        </div>`;
    }).join('');
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

    container.innerHTML = traits.map(t => {
        const cat = (t.category || 'other').toLowerCase();
        const conf = (t.confidence || 'medium').toLowerCase();
        const popFreq = t.population_frequency;

        return `
        <div class="trait-card" data-category="${esc(cat)}">
            <div class="trait-card-name">${esc(t.name || t.trait || '')}</div>
            <div class="trait-card-result">${esc(t.result || t.value || '—')}</div>
            <div class="trait-card-explanation">${esc(t.explanation || t.description || '')}</div>
            <div class="trait-card-meta">
                ${popFreq != null ? `
                    <div class="trait-pop-freq">
                        <div class="trait-pop-freq-label">Pop. frequency: ${(popFreq * 100).toFixed(0)}%</div>
                        <div class="trait-pop-freq-bar"><div class="trait-pop-freq-fill" style="width:${Math.min(100, popFreq * 100)}%"></div></div>
                    </div>` : '<div></div>'}
                <span class="confidence-badge confidence-${conf}">${conf} confidence</span>
            </div>
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
function renderAncestry(ancestry) {
    // Maternal haplogroup
    const mhg = ancestry.maternal_haplogroup || {};
    const mhgName = mhg.name || mhg.haplogroup || '—';
    document.getElementById('maternal-hg-name').textContent = mhgName;
    document.getElementById('maternal-hg-desc').textContent = mhg.description || mhg.geographic_description || '';
    if (mhgName === 'Not available' || mhgName === 'Unknown') {
        document.getElementById('maternal-hg-name').style.color = '#9CA3AF';
    }

    // Paternal haplogroup
    const phg = ancestry.paternal_haplogroup || {};
    document.getElementById('paternal-hg-name').textContent = phg.name || phg.haplogroup || '—';
    document.getElementById('paternal-hg-desc').textContent = phg.description || phg.geographic_description || '';
    // Hide paternal if not available (e.g. female sample)
    document.getElementById('paternal-haplogroup').style.display = (phg.name || phg.haplogroup) ? '' : 'none';

    // Ancestry composition
    const comp = ancestry.composition || [];
    const compSection = document.getElementById('ancestry-composition-section');
    if (comp.length > 0) {
        compSection.style.display = '';
        DNACharts.createAncestryBar('chart-ancestry-bar', comp);
    } else {
        compSection.style.display = 'none';
    }

    // PRS
    const prs = ancestry.prs || [];
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
            DNACharts.createPRSGauge(gaugeContainer, p.percentile || 0, p.condition || '');
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
