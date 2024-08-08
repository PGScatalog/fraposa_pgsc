#! /usr/bin/env python
import csv

import fraposa_pgsc.fraposa as fp
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ref_filepref', help='Prefix of the binary PLINK file for the reference samples.')
    parser.add_argument('--stu_filepref', help='Prefix of the binary PLINK file for the study samples.')
    parser.add_argument('--stu_filt_iid', help='File with list of FIDs and IIDs to extract from the study file (bim format)')
    parser.add_argument('--method', help='The method for PCA prediction. oadp: most accurate. adp: accurate but slow. sp: fast but inaccurate. Default is odap.')
    parser.add_argument('--dim_ref', help='Number of PCs you need.')
    parser.add_argument('--dim_stu', help='Number of PCs predicted for the study samples before doing the Procrustes transformation. Only needed for the oadp and adp methods. Default is 2*dim_ref.')
    parser.add_argument('--dim_online', help='Number of PCs to calculate in online SVD. Only needed for the oadp method. Default is 2*dim_stu')
    parser.add_argument('--dim_rand', help='Number of reference PCs to calculate when using randomized online SVD')
    parser.add_argument('--dim_spikes', help='Number of PCs to adjust for shrinkage. Only needed for the ap method. If this argument is not set, dim_spikes_max will be used.')
    parser.add_argument('--dim_spikes_max', help='The maximal number of PCs to adjust for shrinkage. Only needed for the ap method. This argument will be ignored if dim_spikes is set. Default is 4*dim_ref.')
    parser.add_argument('--out', help='Prefix of output file(s). Default is stu_filepref')
    args=parser.parse_args()

    ref_filepref = args.ref_filepref
    stu_filepref = None
    out_filepref = ref_filepref
    method = 'oadp'
    dim_ref = 4
    dim_stu = None
    dim_online = None
    dim_rand = None
    dim_spikes = None
    dim_spikes_max = None

    if args.stu_filepref:
        stu_filepref = args.stu_filepref
        out_filepref = stu_filepref

    try:
        with open(args.stu_filt_iid) as f:
            reader = csv.reader(f, delimiter="\t") # reads columns as str
            stu_filt_iid = []
            for x in reader:
                stu_filt_iid.append((x[0], x[1])) # return FID, IID
            l_input = len(stu_filt_iid)
            stu_filt_iid = set(stu_filt_iid)
            if l_input != len(stu_filt_iid):
                raise ValueError("Duplicate IDs found in filter list")
    except TypeError:
        stu_filt_iid = None
    except IndexError:
        raise ValueError("Can't parse --stu_filt_iid file (it should be a plink fam file)")

    if args.out:
        out_filepref = args.out
    if args.method:
        method = args.method
    if args.dim_ref:
        dim_ref = int(args.dim_ref)
    if args.dim_stu:
        dim_stu = int(args.dim_stu)
    if args.dim_online:
        dim_online = int(args.dim_online)
    if args.dim_rand:
        dim_rand = int(args.dim_rand)
    if args.dim_spikes:
        dim_spikes = int(args.dim_spikes)
    if args.dim_spikes_max:
        dim_spikes_max = int(args.dim_spikes_max)

    fp.pca(ref_filepref=ref_filepref, stu_filepref=stu_filepref, stu_filt_iid=stu_filt_iid, out_filepref=out_filepref,
           method=method, dim_ref=dim_ref, dim_stu=dim_stu, dim_online=dim_online, dim_rand=dim_rand,
           dim_spikes=dim_spikes, dim_spikes_max=dim_spikes_max)


if __name__ == '__main__':
    main()
