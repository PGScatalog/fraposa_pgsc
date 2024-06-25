# FRAPOSA_PGSC

[![install with bioconda](https://img.shields.io/badge/install%20with-bioconda-brightgreen.svg?style=flat)](http://bioconda.github.io/recipes/fraposa-pgsc/README.html)
[![DOI](https://zenodo.org/badge/610312021.svg)](https://zenodo.org/badge/latestdoi/610312021)

FRAPOSA (Fast and Robust Ancestry Prediction by using Online singular value decomposition and Shrinkage Adjustment)
is a python script to predict the ancestry of study samples by the results of principal component analysis (PCA) on a 
reference panel. The software originally accompanied 
[Zhang, Dey, and Lee. Bionformatics (2020)](https://doi.org/10.1093/bioinformatics/btaa152), but is being adapted here 
for integration with the Polygenic Score (PGS) Catalog pipeline for calculating PGS 
([`pgsc_calc`](https://github.com/PGScatalog/pgsc_calc)).


# Software requirements

- Python 3 (see [`pyproject.toml`](pyproject.toml) for package requirements)
- PLINK ([v1.9](https://www.cog-genomics.org/plink/)) - only needed for data preparation

# Inputs and Outputs

## Input files

- Binary PLINK files for the reference set: `refpref_raw.{bed,bim,fam}`
- Binary PLINK files for the study set: `stupref_raw.{bed,bim,fam}`
  - If no study set is given, FRAPOSA will only run PCA on the reference set and output the reference PC scores.
- Reference population membership: `refpref_raw.popu`
  - Without this file, the study PC scores will still be computed, but you will not be able to predict the population memberships for the study samples.
  - Format
  - Column 1 and 2: Family and individual IDs (same as in `refpref_raw.fam`)
  - Column 3: Population membership label 

## Output files
`fraposa`:
- Reference PC scores: `{refpref}.pcs`
- Study PC scores: `{stupref}.pcs`

`fraposa_pred`:
- Study ancestry memberships: `{stupref}.popu`

`fraposa_plot`:
- PC plot: `{stupref}.png`


# Preprocessing

> [!TIP]
> The preprocessing and analysis steps described below are automated by the [PGS Catalog Calculator](https://github.com/PGScatalog/pgsc_calc)

## Extract common variants

The reference and study samples must have the same set of variants (i.e. the two `.bim` files must be identical).
To extract the common variants between two datasets, you can use PLINK manually or use the included `commvar.sh` script:

```
./commvar.sh refpref_raw stupref_raw refpref stupref
```

This command will find the common variants in `refpref_raw.{bed,bim,fam}` and `stupref_raw.{bed,bim,fam}`
and then output the intersected datasets in `refpref.{bed,bim,fam}` and `stupref.{bed,bim,fam}`. 

> [!IMPORTANT]
> `commvar.sh` requires identical allele orientation between the two datasets.
> In the `pgsc_calc` pipeline we use a more flexible program [`pgscatalog-intersect`](https://github.com/PGScatalog/pygscatalog) to identify common variants

## Split study samples

FRAPOSA loads all the study samples into memory. If the study set is too large, its samples can be split into smaller 
batches. Then FRAPOSA can be run on each batch sequentially or (embarrassingly) parallelly. This can be done by either
(1) only reading a subset of samples from the study `stupref.{bed,bim,fam}` files, or (2) splitting the inputs. 

### 1. Reading a subset of samples
You can determine unique chunks of samples to be read into memory. A `{stupref}.fam` file can be split into sets of 1000 
samples using the following command:
```
cut -f2 -d ' ' {stupref}.fam | split -l 1000 -a 4 - split_ids_
```
This will yield a list of files `split_ids_*` that you can then run in series or in paraellel, for example:
```
fraposa {refpref} # run so that the *dat files are already made and consistent across splits of the study data

for x in split_ids_*; do
  fraposa {refpref} --stu_filepref {stupref} --stu_filt_iid $x --out $x
done
```
This has the benefit of keeping space low - it's better to have pr

### 2. Splitting input files
Just as for extracting the common variants, you can split the study samples manually using PLINK or run the included 
script `splitindiv.sh`: 
```
./splitindiv.sh stupref n i stupref_batch_i
```
which divides the samples in `stupref.{bed,bim,fam}` evenly into `n` batches and saves the samples in batch `i` into 
`stupref_batch_i.{bed,bim,fam}`. For example, if `stupref.{bed,bim,fam}` has 100,000 samples, then
```
./splitindiv.sh stupref 100 12 stupref_batch_12
```
produces `stupref_batch_12.{bed,bim,fam}` that contains sample 12,001 to 13,000. To generate all the 100 batches, 
you can use
```
for i in `seq 1 100`; do
  ./splitindiv.sh stupref 100 $i stupref_batch_$i
done
```

# Running FRAPOSA
To use FRAPOSA with the default settings, run
```
fraposa --stu_filepref stupref refpref 
```
This will produce `refpref.pcs`, which contains the IIDs and reference PC scores, and `stupref.pcs`, which contains 
the IIDs and the study PC scores. Some intermediate files (`*.dat`) are produced to reduce the computation time for 
projections (e.g. in paraellel) and checking that the variants match. The full set of options for the script are:
```
$ fraposa -h
usage: fraposa [-h] [--stu_filepref STU_FILEPREF] [--stu_filt_iid STU_FILT_IID] [--method METHOD] [--dim_ref DIM_REF] [--dim_stu DIM_STU] [--dim_online DIM_ONLINE] [--dim_rand DIM_RAND] [--dim_spikes DIM_SPIKES] [--dim_spikes_max DIM_SPIKES_MAX] [--out OUT] ref_filepref

positional arguments:
  ref_filepref          Prefix of the binary PLINK file for the reference samples.

options:
  -h, --help            show this help message and exit
  --stu_filepref STU_FILEPREF
                        Prefix of the binary PLINK file for the study samples.
  --stu_filt_iid STU_FILT_IID
                        File with list of IIDs to extract from the study file
  --method METHOD       The method for PCA prediction. oadp: most accurate. adp: accurate but slow. sp: fast but inaccurate. Default is odap.
  --dim_ref DIM_REF     Number of PCs you need.
  --dim_stu DIM_STU     Number of PCs predicted for the study samples before doing the Procrustes transformation. Only needed for the oadp and adp methods. Default is 2*dim_ref.
  --dim_online DIM_ONLINE
                        Number of PCs to calculate in online SVD. Only needed for the oadp method. Default is 2*dim_stu
  --dim_rand DIM_RAND   Number of reference PCs to calculate when using randomized online SVD
  --dim_spikes DIM_SPIKES
                        Number of PCs to adjust for shrinkage. Only needed for the ap method. If this argument is not set, dim_spikes_max will be used.
  --dim_spikes_max DIM_SPIKES_MAX
                        The maximal number of PCs to adjust for shrinkage. Only needed for the ap method. This argument will be ignored if dim_spikes is set. Default is 4*dim_ref.
  --out OUT             Prefix of output file(s). Default is stu_filepref

```

## Change analysis method


FRAPOSA_PGSC includes 3 methods for PC score prediction.

1. **OADP** (default and recommended):
This method is fast and provides robust PC score prediction by using the online SVD algorithm.

2. **SP** (fast but inaccurate):
This method is similar to AP and is the standard method of PC prediction. It computes the PC loadings of the reference 
set and projects the (standardized) study samples onto them. Its speed is the same as AP but does not adjust for the 
shrinkage bias, which makes it inaccurate when the number of variants greatly exceeds the sample size. 

3. **ADP** (accurate but slow):
This method is similar to OADP but has a much higher computation complexity. While OADP only computes the top few PCs,
ADP computes all the PCs (i.e. running a full eigendecomposition for every study sample). The results are very close 
to OADP's.


To change the analysis method, set the `--method` option. For example,
```
./fraposa_runner.py --stu_filepref stupref --method sp refpref 
```

The original package also implemented a fourth method that was deprecated to remove the external dependancy on R/hdpca:
1. ~~**AP** (also recommended)~~:
~~This method is even faster and its results are close to OADP's.However, sometimes you may want to manually set the 
number of PCs to be adjusted for shrinkage (i.e. by setting `--dim_spikes`) if you believe that a shrunk PC has not
been adjusted automatically.~~ Required the python package (`rpy2`), an installation of R and the R package (`hdpca`).

## Change the other parameters

Several PCA-related parameters can be changed.
For example, to set the number of reference PCs to 20, run
```
./fraposa_runner.py --stu_filepref stupref --dim_ref 20 refpref 
```
To learn all the options for FRAPOSA, run
```
./fraposa_runner.py --help
```

## Important: Remove the intermediate files

If you have run FRAPOSA previously by using

1. the same reference set, and
2. different parameter settings
(e.g. by changin `--dim_ref` or `--dim_stu`),

then you need to delete all the intermediate `.dat` files with the same prefix as this reference set.

FRAPOSA saves the intermediate files related to PCA on the reference set. Specifically, variants used (`{refpref}_vars.dat`), 
the mean and standard deviation of each variant (`{refpref}_mnsd.dat`), singular values (`{refpref}_s.dat`), reference 
PC loadings (`{refpref}_U.dat`), scaled (`{refpref}.pcs`) and unscaled (`refpref_V.dat`) reference PC scores are saved
and will be automatically loaded if the same reference set is used again. This avoids running PCA on the same reference 
set multiple times, especially in the case when the study samples are split into batches and are analyzed with the same 
reference set.

**WARNING**: FRAPOSA only checks whether the reference set file prefix is the same when deciding whether to load the 
intermediate files. It does *not* detect whether the parameters have been changed.


# Postprocessing

## Predict ancestry memberships

After predicting the study samples' PC scores, their ancestry memberships can also be predicted, if the reference 
ancestry information `refpref.popu` is provided. Running
```
./predstupopu.py refpref stupref
```
will produce `stupref.popu`, which contains

- IDs (columns 1 and 2)
- the population that the study sample most likely belongs to (column 3)
- how likely the study sample belongs to the population in column 3 (column 4)
- The distance between the study sample and the nearest reference sample (column 5)
- How likely the study sample belongs to each of the refrence populations
(columns 6 to 6+q-1, where q is the number of reference populations)
- Names of the refrence populations. This is the same in every row. (columns 6+q to 6+2q-1)

Population prediction is done by using the k-nearest neighbor algorithm
to classify the study PC scores with respect to the reference PC scores.
You can set the number of neighbors or the method for calculating the weights by using
```
./predstupopu.py --nneighbors 20 --weights uniform refpref stupref 
```

## Plot the PC scores
A simple script for plotting the PC scores is included:
```
./plotpcs.py refpref stupref
```
The PC plot will be saved to `refpref.png`.

# Data

An example data set can be found [here](https://upenn.app.box.com/v/fraposa-demo), which includes
- Reference data (`thousandGenomes.{bed,bim,fam,popu}`)
    - This data set contains the 2,492 unrelated samples from the 1000 Genomes project with 637,177 SNPs that are included in the Human Genome Diversity Project. The population memberships of the samples are also provided.
- Study data (`exampleStudySamples.{bed,bim,fam}`)
    -  This data set contains 500 samples with 145,282 SNPs. The ancestry information of these samples can be predicted by FRAPOSA.
