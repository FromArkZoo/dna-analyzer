# Health-variant reference validation (allele-pinned)

Validated **53** curated variants against live ClinVar / gnomAD / dbSNP (GDM science-skills, build-time only). gnomAD SNV lookups are allele-pinned.

## Summary

- Significance **conflicts** (curated pathogenic, ClinVar benign): **2**
- Frequency off by >5x (allele-pinned only counted as solid): **14**
- Proposed (trustworthy) frequency updates: **13**
- Retrieval errors: **2**

## ⚠️ Significance conflicts

| rsid | gene | curated sig | ClinVar (review) | sig verdict | cur freq | gnomAD AF | method | freq verdict |
|---|---|---|---|---|---|---|---|---|
| rs28897727 | BRCA2 | Pathogenic | Benign (reviewed by expert panel) | CONFLICT: curated 'Pathogenic' vs ClinVar 'Benign' | 0.0005 | 6.43e-03 | by-rsid (rsID-confirmed) | off by 13x |
| rs11591147 | PCSK9 | Likely pathogenic | Benign/Likely benign (criteria provided, multiple submitters, no conflicts) | CONFLICT: curated 'Likely pathogenic' vs ClinVar 'Benign/Likely benign' | 0.02 | 1.49e-02 | pinned (direct) | ok |

## Frequency discrepancies

| rsid | gene | curated sig | ClinVar (review) | sig verdict | cur freq | gnomAD AF | method | freq verdict |
|---|---|---|---|---|---|---|---|---|
| rs80357906 | BRCA1 | Pathogenic | Pathogenic (reviewed by expert panel) | match | 0.001 | 6.75e-05 | by-rsid (rsID-confirmed) | off by 15x |
| rs80357914 | BRCA1 | Pathogenic | Pathogenic (reviewed by expert panel) | match | 0.001 | 1.18e-04 | by-rsid (rsID-confirmed) | off by 8x |
| rs28897696 | BRCA2 | Pathogenic | Conflicting classifications of pathogenicity (criteria provided, conflicting classifications) | differs: curated 'Pathogenic' vs ClinVar 'Conflicting classifications of pathogenicity' | 0.001 | 1.98e-05 | by-rsid (rsID-confirmed) | off by 50x |
| rs28897727 | BRCA2 | Pathogenic | Benign (reviewed by expert panel) | CONFLICT: curated 'Pathogenic' vs ClinVar 'Benign' | 0.0005 | 6.43e-03 | by-rsid (rsID-confirmed) | off by 13x |
| rs2187668 | HLA-DQA1 | Risk factor | - () | no ClinVar classification | 0.14 | 3.35e-03 | pinned (direct) | off by 42x |
| rs334 | HBB | Pathogenic | other (no assertion criteria provided) | differs: curated 'Pathogenic' vs ClinVar 'other' | 0.08 | 2.65e-03 | pinned (complement/minus-strand) | off by 30x |
| rs75961395 | CFTR | Pathogenic | Pathogenic (criteria provided, multiple submitters, no conflicts) | match | 0.002 | 6.34e-05 | pinned (direct) | off by 32x |
| rs113993960 | CFTR | Pathogenic | Pathogenic (reviewed by expert panel) | match | 0.001 | 1.19e-02 | by-rsid (rsID-confirmed) | off by 12x |
| rs1050828 | G6PD | Pathogenic | Likely pathogenic (criteria provided, single submitter) | differs: curated 'Pathogenic' vs ClinVar 'Likely pathogenic' | 0.1 | 6.44e-03 | by-rsid (rsID-confirmed) | off by 16x |
| rs5030868 | G6PD | Pathogenic | Likely pathogenic (criteria provided, single submitter) | differs: curated 'Pathogenic' vs ClinVar 'Likely pathogenic' | 0.04 | 1.41e-03 | pinned (complement/minus-strand) | off by 28x |
| rs1801282 | PPARG | Risk factor | Benign/Likely benign (criteria provided, multiple submitters, no conflicts) | differs: curated 'Risk factor' vs ClinVar 'Benign/Likely benign' | 0.85 | 1.13e-01 | pinned (complement/minus-strand) | off by 8x |
| rs10811661 | CDKN2A/B | Risk factor | - () | no ClinVar classification | 0.82 | 1.46e-01 | by-rsid (rsID-confirmed) | off by 6x |
| rs17822931 | ABCC11 | Risk factor | Benign (criteria provided, single submitter) | differs: curated 'Risk factor' vs ClinVar 'Benign' | 0.7 | 1.86e-06 | pinned (complement/minus-strand) | off by 376568x — IMPLAUSIBLE, review curated risk_allele |
| rs662799 | APOA5 | Risk factor | Benign (criteria provided, multiple submitters, no conflicts) | differs: curated 'Risk factor' vs ClinVar 'Benign' | 0.08 | 8.99e-01 | by-rsid (rsID-confirmed) | off by 11x |

## Full results

| rsid | gene | curated sig | ClinVar (review) | sig verdict | cur freq | gnomAD AF | method | freq verdict |
|---|---|---|---|---|---|---|---|---|
| rs80357906 | BRCA1 | Pathogenic | Pathogenic (reviewed by expert panel) | match | 0.001 | 6.75e-05 | by-rsid (rsID-confirmed) | off by 15x |
| rs80357914 | BRCA1 | Pathogenic | Pathogenic (reviewed by expert panel) | match | 0.001 | 1.18e-04 | by-rsid (rsID-confirmed) | off by 8x |
| rs28897696 | BRCA2 | Pathogenic | Conflicting classifications of pathogenicity (criteria provided, conflicting classifications) | differs: curated 'Pathogenic' vs ClinVar 'Conflicting classifications of pathogenicity' | 0.001 | 1.98e-05 | by-rsid (rsID-confirmed) | off by 50x |
| rs28897727 | BRCA2 | Pathogenic | Benign (reviewed by expert panel) | CONFLICT: curated 'Pathogenic' vs ClinVar 'Benign' | 0.0005 | 6.43e-03 | by-rsid (rsID-confirmed) | off by 13x |
| rs80357713 | BRCA1 | Pathogenic | - () | no ClinVar classification | 0.0003 | - | - | gnomAD has no global AF (very rare); unverifiable here |
| rs429358 | APOE | Risk factor | no classification for the single variant (no classification for the single variant) | differs: curated 'Risk factor' vs ClinVar 'no classification for the single variant' | 0.16 | 1.49e-01 | pinned (direct) | ok |
| rs7412 | APOE | Risk factor | Likely pathogenic (criteria provided, single submitter) | differs: curated 'Risk factor' vs ClinVar 'Likely pathogenic' | 0.08 | 7.42e-02 | by-rsid (rsID-confirmed) | ok |
| rs6025 | F5 | Pathogenic | Conflicting classifications of pathogenicity (criteria provided, conflicting classifications) | differs: curated 'Pathogenic' vs ClinVar 'Conflicting classifications of pathogenicity' | 0.05 | 2.14e-02 | pinned (complement/minus-strand) | ok |
| rs1801133 | MTHFR | Risk factor | Benign (criteria provided, multiple submitters, no conflicts) | differs: curated 'Risk factor' vs ClinVar 'Benign' | 0.33 | 3.18e-01 | pinned (direct) | ok |
| rs1801131 | MTHFR | Risk factor | Benign/Likely benign; other (criteria provided, multiple submitters, no conflicts) | differs: curated 'Risk factor' vs ClinVar 'Benign/Likely benign; other' | 0.3 | 3.03e-01 | pinned (direct) | ok |
| rs1800562 | HFE | Pathogenic | Conflicting classifications of pathogenicity; other; risk factor (criteria provided, conflicting classifications) | differs: curated 'Pathogenic' vs ClinVar 'Conflicting classifications of pathogenicity; other; risk factor' | 0.06 | 5.70e-02 | pinned (direct) | ok |
| rs1799945 | HFE | Risk factor | Conflicting classifications of pathogenicity; other (criteria provided, conflicting classifications) | differs: curated 'Risk factor' vs ClinVar 'Conflicting classifications of pathogenicity; other' | 0.14 | 1.32e-01 | pinned (direct) | ok |
| rs2187668 | HLA-DQA1 | Risk factor | - () | no ClinVar classification | 0.14 | 3.35e-03 | pinned (direct) | off by 42x |
| rs10490924 | ARMS2 | Risk factor | risk factor (no assertion criteria provided) | match | 0.22 | 2.31e-01 | pinned (direct) | ok |
| rs1061170 | CFH | Risk factor | Conflicting classifications of pathogenicity (criteria provided, conflicting classifications) | differs: curated 'Risk factor' vs ClinVar 'Conflicting classifications of pathogenicity' | 0.34 | 6.37e-01 | by-rsid (rsID-confirmed) | ok |
| rs28929474 | SERPINA1 | Pathogenic | Likely pathogenic (criteria provided, single submitter) | differs: curated 'Pathogenic' vs ClinVar 'Likely pathogenic' | 0.02 | 1.59e-02 | pinned (complement/minus-strand) | ok |
| rs334 | HBB | Pathogenic | other (no assertion criteria provided) | differs: curated 'Pathogenic' vs ClinVar 'other' | 0.08 | 2.65e-03 | pinned (complement/minus-strand) | off by 30x |
| rs1799963 | F2 | Pathogenic | Pathogenic/Likely pathogenic/Pathogenic, low penetrance/Established risk allele; risk factor (criteria provided, multiple submitters, no conflicts) | differs: curated 'Pathogenic' vs ClinVar 'Pathogenic/Likely pathogenic/Pathogenic, low penetrance/Established risk allele; risk factor' | 0.02 | 1.14e-02 | pinned (direct) | ok |
| rs121909001 | CFTR | Pathogenic | - () | no ClinVar classification | 0.02 | - | - | gnomAD has no global AF (very rare); unverifiable here |
| rs75961395 | CFTR | Pathogenic | Pathogenic (criteria provided, multiple submitters, no conflicts) | match | 0.002 | 6.34e-05 | pinned (direct) | off by 32x |
| rs113993960 | CFTR | Pathogenic | Pathogenic (reviewed by expert panel) | match | 0.001 | 1.19e-02 | by-rsid (rsID-confirmed) | off by 12x |
| rs1050828 | G6PD | Pathogenic | Likely pathogenic (criteria provided, single submitter) | differs: curated 'Pathogenic' vs ClinVar 'Likely pathogenic' | 0.1 | 6.44e-03 | by-rsid (rsID-confirmed) | off by 16x |
| rs5030868 | G6PD | Pathogenic | Likely pathogenic (criteria provided, single submitter) | differs: curated 'Pathogenic' vs ClinVar 'Likely pathogenic' | 0.04 | 1.41e-03 | pinned (complement/minus-strand) | off by 28x |
| rs11591147 | PCSK9 | Likely pathogenic | Benign/Likely benign (criteria provided, multiple submitters, no conflicts) | CONFLICT: curated 'Likely pathogenic' vs ClinVar 'Benign/Likely benign' | 0.02 | 1.49e-02 | pinned (direct) | ok |
| rs515726 | LDLR | Risk factor | - () | no ClinVar classification | 0.1 | 3.49e-01 | by-rsid (rsID-confirmed) | ok |
| rs1042713 | ADRB2 | Risk factor | drug response (reviewed by expert panel) | differs: curated 'Risk factor' vs ClinVar 'drug response' | 0.4 | 3.88e-01 | by-rsid (rsID-confirmed) | ok |
| rs4149056 | SLCO1B1 | Risk factor | drug response (reviewed by expert panel) | differs: curated 'Risk factor' vs ClinVar 'drug response' | 0.14 | 1.42e-01 | pinned (direct) | ok |
| rs12979860 | IFNL3 | Risk factor | drug response (reviewed by expert panel) | differs: curated 'Risk factor' vs ClinVar 'drug response' | 0.3 | 3.10e-01 | pinned (direct) | ok |
| rs1801282 | PPARG | Risk factor | Benign/Likely benign (criteria provided, multiple submitters, no conflicts) | differs: curated 'Risk factor' vs ClinVar 'Benign/Likely benign' | 0.85 | 1.13e-01 | pinned (complement/minus-strand) | off by 8x |
| rs7903146 | TCF7L2 | Risk factor | Likely risk allele (no assertion criteria provided) | differs: curated 'Risk factor' vs ClinVar 'Likely risk allele' | 0.3 | 2.74e-01 | pinned (direct) | ok |
| rs1800497 | ANKK1/DRD2 | Risk factor | Benign (criteria provided, multiple submitters, no conflicts) | differs: curated 'Risk factor' vs ClinVar 'Benign' | 0.2 | 2.23e-01 | pinned (direct) | ok |
| rs1800795 | IL6 | Risk factor | other; risk factor (no assertion criteria provided) | differs: curated 'Risk factor' vs ClinVar 'other; risk factor' | 0.4 | 6.70e-01 | pinned (complement/minus-strand) | ok |
| rs1800629 | TNF | Risk factor | drug response (reviewed by expert panel) | differs: curated 'Risk factor' vs ClinVar 'drug response' | 0.15 | 1.31e-01 | pinned (direct) | ok |
| rs9939609 | FTO | Risk factor | - () | no ClinVar classification | 0.42 | 4.08e-01 | pinned (direct) | ok |
| rs4402960 | IGF2BP2 | Risk factor | risk factor (no assertion criteria provided) | match | 0.3 | 3.76e-01 | pinned (direct) | ok |
| rs10811661 | CDKN2A/B | Risk factor | - () | no ClinVar classification | 0.82 | 1.46e-01 | by-rsid (rsID-confirmed) | off by 6x |
| rs1333049 | CDKN2B-AS1 (9p21) | Risk factor | risk factor (no assertion criteria provided) | match | 0.5 | 4.18e-01 | pinned (direct) | ok |
| rs10757274 | CDKN2B-AS1 (9p21) | Risk factor | risk factor (no assertion criteria provided) | match | 0.48 | 4.15e-01 | pinned (direct) | ok |
| rs2200733 | PITX2 (4q25) | Risk factor | - () | no ClinVar classification | 0.12 | 1.84e-01 | pinned (direct) | ok |
| rs6983267 | 8q24 (MYC enhancer) | Risk factor | - () | no ClinVar classification | 0.5 | 3.82e-01 | by-rsid (rsID-confirmed) | ok |
| rs2981582 | FGFR2 | Risk factor | Benign (criteria provided, single submitter) | differs: curated 'Risk factor' vs ClinVar 'Benign' | 0.4 | 5.84e-01 | by-rsid (rsID-confirmed) | ok |
| rs4880 | SOD2 | Risk factor | Conflicting classifications of pathogenicity; risk factor (no assertion criteria provided) | differs: curated 'Risk factor' vs ClinVar 'Conflicting classifications of pathogenicity; risk factor' | 0.47 | 4.90e-01 | by-rsid (rsID-confirmed) | ok |
| rs1229984 | ADH1B | Risk factor | drug response (reviewed by expert panel) | differs: curated 'Risk factor' vs ClinVar 'drug response' | 0.25 | 9.43e-01 | pinned (direct) | ok |
| rs17822931 | ABCC11 | Risk factor | Benign (criteria provided, single submitter) | differs: curated 'Risk factor' vs ClinVar 'Benign' | 0.7 | 1.86e-06 | pinned (complement/minus-strand) | off by 376568x — IMPLAUSIBLE, review curated risk_allele |
| rs4988235 | MCM6/LCT | Risk factor | association (no assertion criteria provided) | differs: curated 'Risk factor' vs ClinVar 'association' | 0.5 | 3.97e-01 | by-rsid (rsID-confirmed) | ok |
| rs12913832 | HERC2/OCA2 | Risk factor | association (no assertion criteria provided) | differs: curated 'Risk factor' vs ClinVar 'association' | 0.4 | 4.87e-01 | pinned (direct) | ok |
| rs1805007 | MC1R | Risk factor | Conflicting classifications of pathogenicity (criteria provided, conflicting classifications) | differs: curated 'Risk factor' vs ClinVar 'Conflicting classifications of pathogenicity' | 0.08 | 7.49e-02 | pinned (direct) | ok |
| rs1815739 | ACTN3 | Risk factor | Benign (criteria provided, single submitter) | differs: curated 'Risk factor' vs ClinVar 'Benign' | 0.42 | 4.39e-01 | pinned (direct) | ok |
| rs4680 | COMT | Risk factor | Benign (criteria provided, multiple submitters, no conflicts) | differs: curated 'Risk factor' vs ClinVar 'Benign' | 0.5 | 4.90e-01 | pinned (direct) | ok |
| rs4961 | ADD1 | Risk factor | drug response (reviewed by expert panel) | differs: curated 'Risk factor' vs ClinVar 'drug response' | 0.2 | 1.98e-01 | pinned (direct) | ok |
| rs662799 | APOA5 | Risk factor | Benign (criteria provided, multiple submitters, no conflicts) | differs: curated 'Risk factor' vs ClinVar 'Benign' | 0.08 | 8.99e-01 | by-rsid (rsID-confirmed) | off by 11x |
| rs1800896 | IL10 | Risk factor | Pathogenic (criteria provided, single submitter) | differs: curated 'Risk factor' vs ClinVar 'Pathogenic' | 0.45 | 4.01e-01 | by-rsid (rsID-confirmed) | ok |
| rs1695 | GSTP1 | Risk factor | Benign (criteria provided, multiple submitters, no conflicts) | differs: curated 'Risk factor' vs ClinVar 'Benign' | 0.35 | 3.41e-01 | pinned (direct) | ok |

## Retrieval errors

- rs80357713 (BRCA1): gnomad: {"error": "Could not resolve rsID rs80357713"}
- rs121909001 (CFTR): gnomad: {"error": "Could not resolve rsID rs121909001"}