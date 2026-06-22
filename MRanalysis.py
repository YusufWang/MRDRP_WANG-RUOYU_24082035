
import os
import glob
import re
import warnings

import pandas as pd
import seaborn as sns
import rpy2
import rpy2.robjects as robjects

from rpy2.robjects.packages import importr
from rpy2.robjects import pandas2ri
from rpy2.rinterface_lib.embedded import RRuntimeError

warnings.filterwarnings('ignore')
pandas2ri.activate()

primary = "#404040"
accent = "#24B8A0"
pal = sns.color_palette([primary, accent])
style = {
    "axes.edgecolor": primary,
    "axes.labelcolor": primary,
    "text.color": primary,
    "xtick.color": primary,
    "ytick.color": primary,
}

sns.set_palette(pal)
sns.set_context("talk")
sns.set_style("ticks", style)

# Import required R packages
TwoSampleMR = importr("TwoSampleMR")
ieugwasr = importr("ieugwasr")
grdevices = importr("grDevices")

# Get plink binary from genetics.binaRies
plink_binary = robjects.r("genetics.binaRies::get_plink_binary()")

# Generic print function for R plot objects
rprint = robjects.r("function(x, ...) print(x)")


def LD_clump(sig_var_dir, rsid, beta, se, effect_allele, other_allele, eaf, pval,
             ref_genome_file=None, clump_threshold=0.01, population='EUR',
             samplesize=None, chrom=None, pos=None, delimiter=',',
             file_pattern='*.csv', local_clump=False):
    """
    Perform LD clumping for each exposure.
    """

    sig_var_files = sorted(glob.glob(os.path.join(sig_var_dir, file_pattern)))

    exposure_IVs = []
    error_indices = []

    for i in range(len(sig_var_files)):
        try:
            exp_data = TwoSampleMR.read_exposure_data(
                filename=sig_var_files[i],
                clump=False,
                sep=delimiter,
                snp_col=rsid,
                beta_col=beta,
                se_col=se,
                effect_allele_col=effect_allele,
                other_allele_col=other_allele,
                eaf_col=eaf,
                pval_col=pval,
                samplesize_col=samplesize,
                chr_col=chrom,
                pos_col=pos
            )

            if local_clump:
                with (robjects.default_converter + pandas2ri.converter).context():
                    exp_data_py = robjects.conversion.get_conversion().rpy2py(exp_data)

                exp_data_py = exp_data_py.rename(columns={
                    "SNP": "rsid",
                    "pval.exposure": "pval",
                    "id.exposure": "id"
                })

                with (robjects.default_converter + pandas2ri.converter).context():
                    exp_data_r = robjects.conversion.get_conversion().py2rpy(exp_data_py)

                IVs = ieugwasr.ld_clump(
                    dat=exp_data_r,
                    clump_r2=clump_threshold,
                    pop=population,
                    plink_bin=plink_binary,
                    bfile=ref_genome_file
                )

                with (robjects.default_converter + pandas2ri.converter).context():
                    IVs_py = robjects.conversion.get_conversion().rpy2py(IVs)

                IVs_py = IVs_py.rename(columns={
                    "rsid": "SNP",
                    "pval": "pval.exposure",
                    "id": "id.exposure"
                })

                with (robjects.default_converter + pandas2ri.converter).context():
                    IVs = robjects.conversion.get_conversion().py2rpy(IVs_py)

            else:
                IVs = TwoSampleMR.clump_data(
                    exp_data,
                    clump_r2=clump_threshold,
                    pop=population
                )

            exposure_IVs.append(IVs)

        except RRuntimeError as e:
            print(f"Error processing {sig_var_files[i]}: {e}")
            error_indices.append(i)
            continue

    for i in sorted(error_indices, reverse=True):
        del sig_var_files[i]

    updated_exposures = [
        re.sub(r"_full_sig_variants", "", os.path.splitext(os.path.basename(f))[0])
        for f in sig_var_files
    ]

    return exposure_IVs, updated_exposures


def MR_analysis(exposure_IVs, updated_exposures, outcome_gwas, delimiter,
                rsid_outcome, beta_outcome, se_outcome,
                effect_allele_outcome, other_allele_outcome,
                eaf_outcome, pval_outcome,
                res_out=None, data_out=None, pleiotropy_out=None,
                het_out=None, plot_out=None, singleSNP_out=None):
    """
    Perform MR analysis on each exposure with the desired outcome.
    """

    MR_results = []
    MR_data_total = []
    pleiotropy_tests = []
    het_tests = []
    p_all = []
    psingle_all = []

    for i in range(len(exposure_IVs)):
        outcome_dat = TwoSampleMR.read_outcome_data(
            snps=exposure_IVs[i][0],
            filename=outcome_gwas,
            sep=delimiter,
            snp_col=rsid_outcome,
            beta_col=beta_outcome,
            se_col=se_outcome,
            effect_allele_col=effect_allele_outcome,
            other_allele_col=other_allele_outcome,
            eaf_col=eaf_outcome,
            pval_col=pval_outcome
        )

        MR_data = TwoSampleMR.harmonise_data(exposure_IVs[i], outcome_dat)
        res = TwoSampleMR.mr(MR_data)
        pleiotropy = TwoSampleMR.mr_pleiotropy_test(MR_data)
        het = TwoSampleMR.mr_heterogeneity(MR_data)
        res_single = TwoSampleMR.mr_singlesnp(MR_data)
        psingle = TwoSampleMR.mr_forest_plot(res_single)
        p = TwoSampleMR.mr_scatter_plot(res, MR_data)

        with (robjects.default_converter + pandas2ri.converter).context():
            res_py = robjects.conversion.get_conversion().rpy2py(res)
            MR_data_py = robjects.conversion.get_conversion().rpy2py(MR_data)
            pleiotropy_py = robjects.conversion.get_conversion().rpy2py(pleiotropy)
            het_py = robjects.conversion.get_conversion().rpy2py(het)

        if res_out is not None:
            os.makedirs(res_out, exist_ok=True)
            res_py.to_csv(f"{res_out}/{updated_exposures[i]}.csv", index=False)

        if data_out is not None:
            os.makedirs(data_out, exist_ok=True)
            MR_data_py.to_csv(f"{data_out}/{updated_exposures[i]}.csv", index=False)

        if pleiotropy_out is not None:
            os.makedirs(pleiotropy_out, exist_ok=True)
            pleiotropy_py.to_csv(f"{pleiotropy_out}/{updated_exposures[i]}.csv", index=False)

        if het_out is not None:
            os.makedirs(het_out, exist_ok=True)
            het_py.to_csv(f"{het_out}/{updated_exposures[i]}.csv", index=False)

        if plot_out is not None:
            os.makedirs(plot_out, exist_ok=True)
            grdevices.png(file=f"{plot_out}/{updated_exposures[i]}.png", width=1000, height=850)
            rprint(p)
            grdevices.dev_off()

        if singleSNP_out is not None:
            os.makedirs(singleSNP_out, exist_ok=True)
            grdevices.png(file=f"{singleSNP_out}/{updated_exposures[i]}_singleSNP.png", width=1000, height=850)
            rprint(psingle)
            grdevices.dev_off()

        MR_results.append(res_py)
        MR_data_total.append(MR_data_py)
        pleiotropy_tests.append(pleiotropy_py)
        het_tests.append(het_py)
        p_all.append(p)
        psingle_all.append(psingle)

    return MR_results, MR_data_total, pleiotropy_tests, het_tests, p_all, psingle_all
