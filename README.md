# MRDRP: A Mendelian Randomization-based Drug Repurposing Pipeline

MRDRP is a Python-based pipeline for performing Mendelian Randomization (MR) in the context of drug repurposing. It uses summary statistics data to perform two-sample MR analyses between exposures of interest and a relevant outcome. The pipeline iterates through individual "exposure-outcome" relationships and obtains causal estimates between each exposure and the outcome of interest by using the R package [TwoSampleMR](https://mrcieu.github.io/TwoSampleMR/) [[1]](#1).

MRDRP consists of two Python files: MRdata.py and MRanalysis.py. The former handles data retrieval, while the latter tackles the MR analysis itself. Each file contains functions that the user will access to perform MR. Below is a quick outline of the main functions included (see Usage for a full example)

### MRdata.py

At the moment, usage of MRdata.py requires that the user have their exposure summary data organized in the following directory structure:

<img width="621" alt="directoriesMRDRP" src="https://github.com/user-attachments/assets/27c18521-096a-4ac7-bdcd-b384ceae4a6e" />

#### Functions:
* `get_data()` : 
    * retrieves data from main exposure directory

    * returns a list of pandas dataframes for each exposure with summary statistics.

* `select_sig_variants()` :
    * selects significant variants for each exposure, based on a user-defined significance threshold. The user has the option to select either cis-acting or cis+trans-acting variants.

    * Cis-variant analysis is the function default. It is assumed that the user has already collected the chromosomes and genomic positions of the genes of interest; these can be used as an argument in this function (see below example).

    * returns csv files for each exposure containing summary statistics for significant variants

### MRanalysis.py

#### Functions:
* `LD_clump()` :
    * Performs LD clumping on the significant variants of each exposure. Option to do local clumping, or perform clumping by connecting to the remote server used by TwoSampleMR. Default is local clumping.
        * Local clumping requires the user to point to a reference genome file

    * Returns:
         * List of exposure instrumental variables (IVs) for each exposure, as R dataframes
         * List of exposure names for use in the next function (for file-labeling purposes).
         

* `MR_analysis()` :
    * performs MR analysis on clumped variants

    * returns 6 different lists:
        * 4 lists of pandas dataframes for each exposure containing: MR results, harmonized data, pleiotropy tests, heterogeneity tests
        * 2 lists of plots (R objects): MR scatter plots, single-SNP plots

        * Also outputs these products (dataframes + plots) to desired destination directories


## Basic requirements

MRDRP requires the latest versions of Python and R. When using a large amount of data, it is recommended to run the pipeline using more advanced computational resources, such as those offered by supercomputing clusters.

Summary statistics files must include the following minimum information for MR analysis[[1]](#1):
* rsID of each SNP
* effect size
* standard error of the effect size
* effect allele

## Usage

Below are some basic examples of how to use the pipeline, assuming 4 exposures of interest (documentation on each function can be accessed via e.g. `print(MRdata.function.__doc__)` and `print(MRanalysis.function.__doc__)`).

Note: arguments should be changed accordingly based on the user's study

### Data retrieval

```python
import MRdata

### Collect exposure data ###

gwas_all = MRdata.get_data('/path/to/exposures_directory', sep='your_delimiter')

### Previously acquired genomic positions for 4 genes of interest ###

positions_build37 = [(16, 67516474, 67517716), (15, 90328120, 90358633), (14, 20923350, 20925927), (19, 36358801, 36370693)]

### Select significant variants near above positions, expanded by a window of 300 kbp ###

MRdata.select_sig_variants('/path/to/exposures_directory', output_dir='/path/to/output_directory', gwas_list=gwas_all, pval='p-value', POS='POS19', CHROM='CHROM', genomic_coordinates=positions_build37, window=300000)
```

### MR analysis

```python
import MRanalysis

### Perform LD clumping (uses output directory specified in previous step as input) ###

exposure_variants, exposure_names = MRanalysis.LD_clump(siv_var_dir='/path/to/output_directory', rsid='rsid', beta='BETA', se='SE', effect_allele='ALLELE1', other_allele='ALLELE0', eaf='A1FREQ', pval='p-value', ref_genome_file='/path/to/ref_genomefile', samplesize='N', chrom='CHROM', pos='POS19', local_clump=True)

### Perform MR analysis ###

mrresults, mrdat, pleiotropy, heterogeneity, plots, plots_singleSNP = MRanalysis.MR_analysis(exposure_variants, exposure_names, '/path/to/outcome_GWAS', delimiter='\t', rsid_outcome='rsID', beta_outcome='EFFECT_SIZE', se_outcome='SE', effect_allele_outcome='ALT', other_allele_outcome='REF', eaf_outcome='POOLED_ALT_AF', pval_outcome='pvalue', res_out='/MRresults/destination', data_out='/harmonized_data/destination', pleiotropy_out='/pleiotropy_tests/destination', het_out='/heterogeneity_tests/destination', plot_out='/MR_scatterplots/destination', singleSNP_out='/singleSNP_plots/destination')


### User's code here to manipulate previous output, select results for exposures with significant MR estimates, etc. ###

```

## References
<a id="1">[1]</a> 
Hemani G, Zheng J, Elsworth B, Wade KH, Baird D, Haberland V, Laurin C, Burgess S, Bowden J, Langdon R, Tan VY, Yarmolinsky J, Shihab HA, Timpson NJ, Evans DM, Relton C, Martin RM, Davey Smith G, Gaunt TR, Haycock PC, The MR-Base Collaboration.
The MR-Base platform supports systematic causal inference across the human phenome.
eLife 2018;7:e34408. doi: 10.7554/eLife.34408
