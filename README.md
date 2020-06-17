FRAPOSA (Fast and Robutst Ancestry Prediction by using Online singular value decomposition and Shrinkage Adjustment) is a software designed for predicting the ancestry of study samples by using a reference panel.
Both the study and the reference samples must be stored in binary PLINK files.
The programs should be run in Python3.

# Preprocessing

## Intersect the variants of the reference and the study samples

Before using FRAPOSA,
the reference samples and the study samples must have the same set of variants
(i.e. the two .bim files are identical).
This can be achieved by using the script `commvar.sh` as follows:
```
bash commvar.sh ref_bedprefix stu_bedprefix ref_bedprefix_comm stu_bedprefix_comm
```

## Split the study data set into smaller ones by samples 

If the study data set is too large to load into memory,
you can split it into multiple data sets with fewer samples in each.
This can be done by using the `splitindiv.sh` script.
For example, if `stu_bedprefix_comm` has 100,000 samples,
then to extract samples 12,000 - 13,300, you can run
```
bash splitindiv.sh stu_bedprefix_comm 100 12
```
To generate all the 100 smaller study sets, create a bash script to run splitindiv.sh in a for loop:
```
for i in `seq 1 1000`; do
  bash splitindiv.sh stu_bedprefix_comm 1000 $i
done;
```

# FRAPOSA

## Required files

- Binary PLINK files for the reference set: ref_bedprefix_comm.{bed,bim,fam}
- Binary PLINK files for the study set: stu_bedprefix_comm.{bed,bim,fam}
  - If no study set is given, FRAPOSA will only run PCA on the reference set and output the reference PC scores.
- Population file for the reference set: ref_bedprefix_comm.popu
  - Without this file, the study PC scores will still be computed, but you will not be able to predict the population memberships for the study samples. (See below.)
  - The first two columns should be the same as those in ref_bedprefix_comm.fam
  - The third column should be the label for the population


## Running the scripts

To use FRAPOSA with default settings, run
```
python fraposa_runner.py --stu_filepref stu_bedprefix_comm ref_bedprefix_comm 
```


To change the method for predicting study PC scores, use
```
python fraposa_runner.py --stu_filepref stu_bedprefix_comm --method=ap ref_bedprefix_comm 
```
There are four methods available:
1. **oadp** (recommended):
This is the default. It is accurate and fast.

2. **ap** (recommended):
Use this if you want something even faster.
This has been proven to be as accurate as oadp in most of the cases we have tried,
but sometimes you may want to manually set the number of PCs to be adjusted for shrinkage (i.e. dim_spikes)
if you believe that a PC has been shrinked but has not been adjusted automatically.

3. **sp** (fast but inaccurate):
The standard way of PCA prediction (i.e. find the PC loadings of the reference samples and project study samples onto them).
It is similar to ap but does not adjust for the shrinkage bias, which makes it much less accurate when the number of variants is large.
The speed is the same as ap.

4. **adp** (accurate but slow):
This is essentially the same as oadp but does not uses a traditional SVD method rather than an online SVD method for PCA prediction.
The accuracy is very close to oadp.

Several parameters in FRAPOSA can be changed. For example, to set the number of reference PCs to 20, run
```
python fraposa_runner.py --stu_filepref stu_bedprefix_comm --dim_ref=20 ref_bedprefix_comm 
```
To learn all the options for FRAPOSA, run
```
python fraposa_runner.py --help
```

**Important**:
If you have run FRAPOSA previously by using the same reference data but different parameter settings,
please delete all the .dat files in the directory of the reference data.
The .dat files store the PCA result of the reference samples in order to avoid repetitive calculation
when you change the study data but use the same reference data.
However, if you have changed the parameter settings,
FRAPOSA would not know that the .dat files have not been updated for the new settings.


# Postprocessing

## Predict study population

If the ancestry membership is provided for the reference samples,
the ancestry membership of the study samples can be predicted.
First, store the reference samples' ancestry membership (e.g. east_asian, european) in a single-column file,
where the order of the rows must match with that in the reference .fam file.
Then run
```
python predstupopu.py ref_bedprefix_comm stu_bedprefix_comm
```
This script uses the k-nearest neighbor algorithm to classify the study samples.
You can set the number of neighbors or the method for calculating the weights by using
```
python predstupopu.py ref_bedprefix_comm stu_bedprefix_comm --nneighbors=20 --weights=uniform
```

## Plot the PC scores
A simple script for plotting the reference PC scores is included:
```
python plotpcs.py ref_bedprefix_comm stu_bedprefix_comm
```

# Reference data

We have provided a reference data set (umich.edu/~daiweiz/fraposa/data/) for your convenience.
We took the 2,492 unrelated samples from the 1000 Genomes project and selected the 637,177 SNPs that are included in the Human Genome Diversity Project.
The population membership of the samples are also included.
