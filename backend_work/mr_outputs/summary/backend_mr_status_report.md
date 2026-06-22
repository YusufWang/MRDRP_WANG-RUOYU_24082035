# Backend MR Status Report

Run time: 2026-05-13 08:18:08

## Target analysis setting

Exposures:
- IGF1
- SHBG
- ADIPOQ
- GDF15

Outcome: endometrial_cancer

## Significant variant selection

| file                        |   rows |   unique_snps |        min_p |       max_p | example_snp     |
|:----------------------------|-------:|--------------:|-------------:|------------:|:----------------|
| GDF15_full_sig_variants.csv |     81 |            81 | 1.67e-105    | 3.207e-08   | 19:18388639:T:G |
| SHBG_full_sig_variants.csv  |      8 |             8 | 2.22507e-307 | 4.43821e-09 | 17:7631360:T:C  |

## Important backend note

At p < 5e-8, cis significant variants were detected for GDF15 and SHBG only. IGF1 and ADIPOQ did not generate significant variant files under the strict threshold. The current available variants use coordinate-based identifiers rather than standard rsID for some files. Therefore, the current MR run uses coordinate-based SNP matching and skips formal LD clumping. This is suitable for backend connectivity testing and prototype result generation, but formal MR should later use rsID-based files or rsID mapping for proper LD clumping.

## SNP overlap

| trait   |   exposure_snps |   outcome_snps |   overlap_snps | example_overlap   |
|:--------|----------------:|---------------:|---------------:|:------------------|
| GDF15   |              81 |          70453 |              2 | 19:18264536       |
| SHBG    |               8 |          70453 |              5 | 17:7387376        |

## MR run summary

| trait   | status   |   harmonised_snps |   result_rows | error   |
|:--------|:---------|------------------:|--------------:|:--------|
| GDF15   | success  |                 2 |             1 |         |
| SHBG    | success  |                 5 |             5 |         |

## Combined MR results

| id.exposure   | id.outcome   | outcome   | exposure   | method                    |   nsnp |         b |       se |      pval | trait   |   MR_OR |   MR_OR_lower_95CI |   MR_OR_upper_95CI | nominal_significant   |
|:--------------|:-------------|:----------|:-----------|:--------------------------|-------:|----------:|---------:|----------:|:--------|--------:|-------------------:|-------------------:|:----------------------|
| sFtvLK        | OMEknY       | outcome   | exposure   | Inverse variance weighted |      2 | -0.704855 | 0.40822  | 0.0842295 | GDF15   | 0.49418 |          0.222025  |            1.09994 | False                 |
| D0KulX        | hEfA5r       | outcome   | exposure   | MR Egger                  |      5 |  0.149544 | 0.220549 | 0.546353  | SHBG    | 1.1613  |          0.753721  |            1.78929 | False                 |
| D0KulX        | hEfA5r       | outcome   | exposure   | Weighted median           |      5 |  0.19828  | 0.202096 | 0.326535  | SHBG    | 1.2193  |          0.82051   |            1.81192 | False                 |
| D0KulX        | hEfA5r       | outcome   | exposure   | Inverse variance weighted |      5 |  0.216414 | 0.20399  | 0.288733  | SHBG    | 1.24162 |          0.83243   |            1.85194 | False                 |
| D0KulX        | hEfA5r       | outcome   | exposure   | Simple mode               |      5 |  0.926519 | 1.74812  | 0.624162  | SHBG    | 2.5257  |          0.0821013 |           77.6988  | False                 |
| D0KulX        | hEfA5r       | outcome   | exposure   | Weighted mode             |      5 |  0.199689 | 2.18519  | 0.931582  | SHBG    | 1.22102 |          0.0168521 |           88.4697  | False                 |
