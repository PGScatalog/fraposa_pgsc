## FRAPOSA: Fast and Robust Ancestry Prediction by Online singular value decomposition and Shrinkage Adjustment
## Original Author: David (Daiwei) Zhang
## Modifications: Samuel Lambert

import matplotlib
import numpy as np
import pandas as pd
from pyplink import PyPlink
from sklearn.neighbors import KNeighborsClassifier

from fraposa_pgsc.variants import MatchType, Variants

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import os.path
import time
from datetime import datetime
import sys
import logging
from sklearn.utils.extmath import randomized_svd
from typing import Union


def create_logger(out_filepref='fraposa'):
    log = logging.getLogger()
    log.handlers = [] # Avoid duplicated logs in interactive modes
    log_level = logging.INFO
    log.setLevel(logging.INFO)
    # create file handler which logs even debug messages
    filename = os.path.join(out_filepref + '.log')
    fh = logging.FileHandler(filename, 'w')
    fh.setLevel(log_level)
    log.addHandler(fh)
    # create console handler with a higher log level
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(log_level)
    log.addHandler(ch)
    return log


def svd_eigcov(XTX):
    ssq, V = np.linalg.eigh(XTX)
    V = np.squeeze(V)
    ssq = np.squeeze(ssq)
    s = np.sqrt(abs(ssq))
    V = V.T[::-1].T
    s = s[::-1]
    return s, V


def svd_online(U1, d1, V1, b, l=None):
    n, k = V1.shape
    if l is None:
        l = k
    assert U1.shape[1] == k
    assert len(d1) == k
    assert(l <= k)
    p = U1.shape[0]
    b = b.reshape((p,1)) # Make sure the new sample is a column vec
    b_tilde = b - U1 @ (U1.T @ b)
    b_tilde = b_tilde / np.sqrt(sum(np.square(b_tilde)))
    R = np.concatenate((np.diag(d1), U1.transpose() @ b), axis = 1)
    R_tail = np.concatenate((np.zeros((1,k)), b_tilde.transpose() @ b), axis = 1)
    R = np.concatenate((R, R_tail), axis = 0)
    d2, R_Vt = np.linalg.svd(R, full_matrices=False)[1:]
    # TODO: Try using chomsky decomposition on R to speed up
    # Since R is triangular
    # Eigencomposition's runtime is the same as svd's
    # d2, R_V = svd_eigcov(R.T @ R)
    # R_Vt = R_V.T
    V_new = np.zeros((k+1, n+1))
    V_new[:k, :n] = V1.transpose()
    V_new[k, n] = 1
    V2 = (R_Vt @ V_new).transpose()[:,:l]
    return d2, V2


def procrustes(Y_mat, X_mat, return_transformed=False):
    ''' Find the best transformation from X to Y '''
    X = np.array(X_mat, dtype=np.double, copy=True)
    Y = np.array(Y_mat, dtype=np.double, copy=True)
    n_X = X.shape[0]
    X_mean = np.mean(X, 0)
    Y_mean = np.mean(Y, 0)
    X -= X_mean
    Y -= Y_mean
    C = Y.T @ X
    U, s, VT = np.linalg.svd(C, full_matrices=False)
    trXX = np.sum(X**2)
    trS = np.sum(s)
    R = VT.T @ U.T
    rho = trS / trXX
    c = Y_mean - rho * X_mean @ R
    if return_transformed:
        X_new = X_mat @ R * rho + c
        return R, rho, c, X_new
    else:
        return R, rho, c


def procrustes_diffdim(Y_mat, X_mat, n_iter_max=10000, epsilon_min=1e-6, return_transformed=False):
    X = np.array(X_mat, dtype=np.double, copy=True)
    Y = np.array(Y_mat, dtype=np.double, copy=True)
    n_X, p_X = X.shape
    n_Y, p_Y = Y.shape
    assert n_X == n_Y
    assert p_X >= p_Y
    if p_X == p_Y:
        return procrustes(Y, X, return_transformed)
    else:
        Z = np.zeros((n_X, p_X - p_Y))
        for i in range(n_iter_max):
            W = np.hstack((Y, Z))
            R, rho, c = procrustes(W, X)
            X_new = X @ R * rho + c
            Z_new = X_new[:, p_Y:]
            Z_new_mean = np.mean(Z_new, 0)
            Z_new_centered = Z_new - Z_new_mean
            Z_diff = Z_new - Z
            epsilon = np.sum(Z_diff**2) / np.sum(Z_new_centered**2)
            if(epsilon < epsilon_min):
                break
            else:
                Z = Z_new
        if return_transformed:
            return R, rho, c, X_new
        else:
            return R, rho, c


def read_bed(bed_filepref, dtype=np.int8, filt_iid=None):
    pyp = PyPlink(bed_filepref)
    bim = pyp.get_bim()
    fam = pyp.get_fam()
    p = len(bim)
    n = len(fam)

    if filt_iid:
        fam_ids = list(zip(fam['fid'], fam['iid'])) # create tuples of ids from genotyping files
        fam_mask = [x in filt_iid for x in fam_ids] # T/F overlap of genotype data and filter IDs (tuples)
        n_matched = sum(fam_mask)
        if n_matched == 0:
            raise ValueError(f"ERROR: 0 / {len(filt_iid)} ids in filter list match the study dataset")
        elif len(set(fam_ids)) != len(fam):
            raise ValueError("Samples with duplicated FID + IID detected, please remove and retry")

        bed = np.zeros(shape=(p, n_matched), dtype=dtype)
        i_extract = [i for i,x in enumerate(fam_mask) if x is True] # idx to extract from genotype matrix
        for (i, (snp, genotypes)) in enumerate(pyp):
            bed[i,:] = genotypes[i_extract]
        fam = fam.loc[fam_mask,:]
        if n_matched < len(filt_iid):
            logging.warning('Warning: only {} / {} ids in filter list match the study dataset'.format(n_matched,
                                                                                                      len(filt_iid)))
        else:
            logging.info('Extracted {} samples from study genotyping data'.format(n_matched))
    else:
        bed = np.zeros(shape=(p, n), dtype=dtype)
        for (i, (snp, genotypes)) in enumerate(pyp):
            bed[i,:] = genotypes
    pyp.close()
    # for i in range(p):
    #     for j in range(n):
    #         bed[i,j] = 2 - bed[i,j]
    # bed = 2 - bed
    bed *= -1
    bed += 2
    return bed, bim, fam


def bim_varlist(bim):
    compcols = ['chrom', 'pos', 'a1', 'a2']
    return [':'.join(map(str, row) )for i, row in bim[compcols].iterrows()]


def compare_variants(ref_variants: Union[pd.DataFrame, list[str]],
                     study_variants: Union[pd.DataFrame, list[str]]) -> Variants:
    """Function to ensure that the variants are consistently ordered across files"""
    ref_vars: list[str]
    stu_vars: list[str]
    match (ref_variants, study_variants):
        case (pd.DataFrame(), pd.DataFrame()):
            ref_vars = bim_varlist(ref_variants)
            stu_vars = bim_varlist(study_variants)
        case (list(), list()):
            ref_vars = ref_variants
            stu_vars = study_variants
        case _:
            raise TypeError(f"Invalid variant types: {type(ref_variants)} and {type(study_variants)}")

    match_type: MatchType = check_varlist(ref_vars, stu_vars)
    ref_indexed: dict[str: int] = {variant: index for index, variant in enumerate(ref_vars)}
    stu_indexed: list[int] = [ref_indexed[variant] for variant in stu_vars]
    ordered_stu_vars: list[str]

    match match_type:
        case MatchType.DIFFERENT_SIZE:
            logging.critical(
                f"ABORT: Different number of variants between reference ({len(ref_vars)}) and study ({len(stu_vars)}) datasets.")
            sys.exit(1)
        case MatchType.DIFFERENT_ID:
            logging.critical("ABORT: Variants do not match across bim files (comp keys: {'chrom', 'pos', 'a1', 'a2'})")
            sys.exit(1)
        case MatchType.ORDERED:
            logging.info("Variants match across reference and study datasets")
            ordered_stu_vars = ref_vars
        case MatchType.DIFFERENT_ORDER:
            logging.warning("Re-ordering study variants")
            ordered_stu_vars = sorted(stu_vars, key=ref_indexed.get)
        case _:
            raise TypeError(f"Invalid match type {match_type}")

    return Variants(reference_variants=ref_vars,
                    study_variants=ordered_stu_vars,
                    match_type=match_type,
                    study_indexes=stu_indexed)


def check_varlist(ref_vl: list[str], stu_vl: list[str]) -> MatchType:
    if len(ref_vl) != len(stu_vl):
        return MatchType.DIFFERENT_SIZE

    if ref_vl != stu_vl:
        if set(ref_vl).difference(set(stu_vl)):
            return MatchType.DIFFERENT_ID
        else:
            return MatchType.DIFFERENT_ORDER

    return MatchType.ORDERED


def save_vars_bim(bim, loc_output):
    with open(loc_output, 'w') as outf:
        outf.write('\n'.join(bim_varlist(bim)))


def standardize(X, mean=None, std=None, miss=3):
    assert np.issubdtype(X.dtype, np.floating)
    p, n = X.shape
    is_miss = X == miss
    if (mean is None) or (std is None):
        mean = np.zeros(p)
        std = np.zeros(p)
        for i in range(p):
            row_nomiss = X[i,:][~is_miss[i,:]]
            mean[i] = np.mean(row_nomiss)
            std[i] = np.std(row_nomiss)
        std[std == 0] = 1
    mean = mean.reshape((-1, 1))
    std = std.reshape((-1, 1))
    X -= mean
    X /= std
    X[is_miss] = 0
    return mean, std


def eig_ref(X):
    print('Calculating reference covariance matrix...')
    XTX = X.T @ X
    print('Eigendecomposition on reference covariance matrix...')
    s, V = svd_eigcov(XTX)
    return s, V, XTX


def ref_aug_procrustes(pcs_ref, pcs_aug):
    n_ref, p_ref = pcs_ref.shape
    n_aug, p_aug = pcs_aug.shape
    assert n_aug == n_ref + 1
    assert p_aug >= p_ref
    pcs_aug_head = pcs_aug[:-1, :]
    pcs_aug_tail = pcs_aug[-1, :].reshape((1,-1))
    R, rho, c = procrustes_diffdim(pcs_ref, pcs_aug_head)
    pcs_aug_tail_trsfed = pcs_aug_tail @ R * rho + c
    return pcs_aug_tail_trsfed.flatten()


def oadp(U, s, V, b, dim_ref=4, dim_stu=None, dim_online=None):
    if dim_stu is None:
        dim_stu = dim_ref * 2
    if dim_online is None:
        dim_online = dim_stu * 2
    pcs_ref = V[:, :dim_ref] * s[:dim_ref]
    s_aug, V_aug = svd_online(U[:,:dim_online], s[:dim_online], V[:,:dim_online], b)
    s_aug, V_aug = s_aug[:dim_stu], V_aug[:, :dim_stu]
    pcs_aug = V_aug * s_aug
    pcs_stu = ref_aug_procrustes(pcs_ref, pcs_aug)
    return pcs_stu[:dim_ref]


def adp(XTX, X, w, pcs_ref, dim_stu=None):
    dim_ref = pcs_ref.shape[1]
    if dim_stu is None:
        dim_stu = dim_ref * 2
    w = w.reshape((-1,1))
    XTw = X.T @ w
    wTw = w.T @ w
    XTX_aug = np.vstack((np.hstack((XTX, XTw)), np.hstack((XTw.T, wTw))))
    s_aug, V_aug = svd_eigcov(XTX_aug)
    s_aug = s_aug[:dim_stu]
    V_aug = V_aug[:, :dim_stu]
    pcs_aug = V_aug * s_aug
    pcs_stu = ref_aug_procrustes(pcs_ref, pcs_aug)
    return pcs_stu[:dim_ref]


def pca_stu(W, X_mean, X_std, method,
            U=None, s=None, V=None, XTX=None, X=None, pcs_ref=None,
            dim_ref=None, dim_stu=None, dim_online=None):
    p_ref = len(X_mean)
    p_stu, n_stu = W.shape
    pcs_stu = np.zeros((n_stu, dim_ref))

    if method == 'oadp':
        assert all([a is not None for a in [U, s, V, dim_ref, dim_stu, dim_online]])
    if method == 'ap':
        assert all([a is not None for a in [U, dim_ref]])
    if method == 'sp':
        assert all([a is not None for a in [U, dim_ref]])
    if method == 'adp':
        assert all([a is not None for a in [XTX, X, pcs_ref, dim_ref, dim_stu]])

    reporting_chunk = (n_stu // 10)
    if reporting_chunk == 0:
        reporting_chunk = 1

    for i in range(n_stu):
        w = W[:,i].astype(np.float64).reshape((-1,1))
        standardize(w, X_mean, X_std, miss=3)
        if method == 'oadp':
            pcs_stu[i,:] = oadp(U, s, V, w, dim_ref, dim_stu, dim_online)
        if method =='sp' or method == 'ap':
            pcs_stu[i,:] = w.T @ U[:,:dim_ref]
        if method =='adp':
            pcs_stu[i,:] = adp(XTX, X, w, pcs_ref, dim_stu=dim_stu)
        if (i+1) % reporting_chunk == 0:
            logging.info('Finished {} out of {} study samples.'.format(i+1, n_stu))

    del W
    return pcs_stu


def _write_pcs(df_pcs, df_fam, colnames, filepref, output_fmt, stage='REFERENCE'):
    pcs_ref = pd.DataFrame(data=df_pcs, index=df_fam[["fid", "iid"]], columns=colnames)
    pcs_ref.index = pd.MultiIndex.from_tuples(pcs_ref.index, names=['FID', 'IID'])
    pcs_ref = pcs_ref.reset_index()  # index to normal columns

    # FID is always a string
    if all(pcs_ref["FID"] == "0"):
        # column is present but missing data
        pcs_ref["FID"] = pcs_ref["IID"]

    pcs_ref.to_csv(filepref + '.pcs', sep='\t', header=True, index=False, float_format=output_fmt)
    logging.info('{} PC scores saved to {}.pcs'.format(stage, filepref))


def _load_pcs_ref(ref_filepref):
    """Returns numpy array from pcs file that has row/column names"""
    return pd.read_csv(ref_filepref + '.pcs', sep='\t', index_col=0).to_numpy()


def _load_mnsd(ref_filepref):
    """Loads normalization factors (mean/std) from saved _mnsd.dat file"""
    Xmnsd = np.loadtxt(ref_filepref + '_mnsd.dat')
    X_mean = Xmnsd[:, 0].reshape((-1, 1))
    X_std = Xmnsd[:, 1].reshape((-1, 1))
    return X_mean, X_std


def pca(ref_filepref, stu_filepref=None, stu_filt_iid=None, out_filepref=None, method='oadp',
        dim_ref=4, dim_stu=None, dim_online=None, dim_rand=None, dim_spikes=None, dim_spikes_max=None):

    create_logger(out_filepref)
    assert method in ['randoadp', 'oadp', 'ap', 'adp', 'sp']
    if method in ['oadp', 'adp']:
        if dim_stu is None:
            dim_stu = dim_ref * 2
        assert dim_ref <= dim_stu
    if method in ['oadp', 'randoadp']:
        if dim_online is None:
            dim_online = dim_stu * 2
        if dim_rand is None:
            dim_rand = dim_online * 2
        assert dim_stu <= dim_online <= dim_rand
    # if method == 'ap':
    #     if dim_spikes is None and dim_spikes_max is None:
    #         dim_spikes_max = dim_ref * 4
    output_fmt = '%.4f'

    logging.info('FRAPOSA started.')
    logging.info('Reference data: {}'.format(ref_filepref))
    logging.info('Study data: {}'.format(stu_filepref))
    logging.info('Output prefix: {}'.format(out_filepref))
    logging.info('Method: {}'.format(method))
    logging.info('Reference dimension: {}'.format(dim_ref))
    colnames_pcs = ['PC{}'.format(x + 1) for x in range(dim_ref)]
    if method in ['oadp', 'adp']:
        logging.info('Study dimension: {}'.format(dim_stu))
    if method == 'oadp':
        logging.info('Online SVD dimension: {}'.format(dim_online))
    if method == 'ap':
        # if dim_spikes is None:
        #     logging.info('Number of distant spikes (max={}) will be estimated by HDPCA.'.format(dim_spikes_max))
        # else:
        #     logging.info('Number of distant spikes: {}'.format(dim_spikes))
        logging.error('Support for the bias-adjusted projection (method=ap) has been removed '
                      'from this version of FRAPOSA! Please use the default online augmentation, decomposition and '
                      'Procrustes (oadp) method.')
        sys.exit(1)

    logging.info(datetime.now())
    if method in ['oadp', 'randoadp']:
        try:
            logging.info('Attemping to load saved reference PCA result...')
            X_mean, X_std = _load_mnsd(ref_filepref)
            s = np.loadtxt(ref_filepref+'_s.dat')
            U = np.loadtxt(ref_filepref+'_U.dat')[:, :dim_online]
            V = np.loadtxt(ref_filepref+'_V.dat')[:, :dim_online]
            pcs_ref = _load_pcs_ref(ref_filepref)[:, :dim_ref]
            logging.info('Warning: If you have changed the parameter settings, please delete '
                         + ref_filepref + '_*.dat and ' + ref_filepref + '.pcs then rerun FRAPOSA.')
            logging.info('Reference PCA result successfully loaded.')
        except OSError:
            logging.info('REFERENCE PCA result is either nonexistent or incomplete.')
            logging.info('Calculating REFERENCE PCA....')
            X, X_bim, X_fam = read_bed(ref_filepref, dtype=np.float32)
            X_mean, X_std = standardize(X)
            if method == 'oadp':
                s, V = eig_ref(X)[:2]
            elif method == 'randoadp':
                s, V = randomized_svd(X, dim_rand)[:2]
            V = V[:, :dim_online]
            pcs_ref = V[:, :dim_ref] * s[:dim_ref]
            U = X @ (V / s[:dim_online])
            np.savetxt(ref_filepref+'_mnsd.dat', np.hstack((X_mean, X_std)), fmt=output_fmt)
            np.savetxt(ref_filepref+'_s.dat', s, fmt=output_fmt)
            np.savetxt(ref_filepref+'_V.dat', V, fmt=output_fmt)
            np.savetxt(ref_filepref+'_U.dat', U, fmt=output_fmt)
            _write_pcs(pcs_ref, X_fam, colnames_pcs, ref_filepref, output_fmt)
            save_vars_bim(X_bim, ref_filepref+'_vars.dat')
        pca_stu_kwargs = {'U':U, 's':s, 'V':V, 'pcs_ref':pcs_ref, 'dim_ref':dim_ref, 'dim_stu':dim_stu, 'dim_online':dim_online}

    # Commented to remove requirement for R
    # if method == 'ap':
    #     try:
    #         logging.info('Attemping to load saved reference PCA result...')
    #         Xmnsd = np.loadtxt(ref_filepref+'_mnsd.dat')
    #         X_mean = Xmnsd[:,0].reshape((-1,1))
    #         X_std = Xmnsd[:,1].reshape((-1,1))
    #         Ushrink = np.loadtxt(ref_filepref+'_Ushrink.dat')[:, :dim_ref]
    #         logging.info('Warning: If you have changed the parameter settings, please delete ' + ref_filepref + '_*.dat and rerun FRAPOSA.')
    #         logging.info('Reference PCA result loaded.')
    #     except OSError:
    #         logging.info('Reference PCA result is either nonexistent or incomplete.')
    #         logging.info('Calculating reference PCA....')
    #         X, X_bim, X_fam = read_bed(ref_filepref, dtype=np.float32)
    #         X_mean, X_std = standardize(X)
    #         s, V = eig_ref(X)[:2]
    #         V = V[:, :dim_ref]
    #         pcs_ref = V[:, :dim_ref] * s[:dim_ref]
    #         Ushrink = X @ (V / s[:dim_ref])
    #         p_ref, n_ref = X.shape
    #         shrinkage = hdpca_shrinkage(s, p_ref, n_ref, dim_spikes=dim_spikes, dim_spikes_max=dim_spikes_max)
    #         n_pc_adjusted = min(dim_ref, len(shrinkage))
    #         logging.info('The top {} out of the {} PCs have been adjusted for shrinkage.'.format(n_pc_adjusted, dim_ref))
    #         logging.info('Shrinkage factors:')
    #         logging.info(shrinkage[:n_pc_adjusted])
    #         for i in range(n_pc_adjusted):
    #             Ushrink[:, i] /= shrinkage[i]
    #         np.savetxt(ref_filepref+'_mnsd.dat', np.hstack((X_mean, X_std)), fmt=output_fmt)
    #         np.savetxt(ref_filepref+'_Vs.dat', pcs_ref, fmt=output_fmt)
    #         np.savetxt(ref_filepref+'_Ushrink.dat', Ushrink, fmt=output_fmt)
    #         logging.info('Reference PC scores saved to ' + ref_filepref + '.pcs')
    #         save_vars_bim(X_bim, ref_filepref + '_vars.dat')
    #     pca_stu_kwargs = {'U':Ushrink, 'dim_ref':dim_ref}

    if method == 'sp':
        saved_filesuffs = ['_mnsd.dat', '_U.dat']
        saved_allexist = all([os.path.isfile(ref_filepref+suff) for suff in saved_filesuffs])
        try:
            logging.info('Attemping to load saved reference PCA result...')
            X_mean, X_std = _load_mnsd(ref_filepref)
            U = np.loadtxt(ref_filepref+'_U.dat')[:, :dim_ref]
            logging.info('Warning: If you have changed the parameter settings, please delete '
                         + ref_filepref + '_*.dat and ' + ref_filepref + '.pcs then rerun FRAPOSA.')
            logging.info('Reference PCA result loaded.')
        except OSError:
            logging.info('REFERENCE PCA result is either nonexistent or incomplete.')
            logging.info('Calculating REFERENCE PCA....')
            X, X_bim, X_fam = read_bed(ref_filepref, dtype=np.float32)
            X_mean, X_std = standardize(X)
            s, V = eig_ref(X)[:2]
            V = V[:, :dim_ref]
            pcs_ref = V[:, :dim_ref] * s[:dim_ref]
            U = X @ (V / s[:dim_ref])
            np.savetxt(ref_filepref+'_mnsd.dat', np.hstack((X_mean, X_std)), fmt=output_fmt)
            _write_pcs(pcs_ref, X_fam, colnames_pcs, ref_filepref, output_fmt)
            np.savetxt(ref_filepref+'_U.dat', U, fmt=output_fmt)
            save_vars_bim(X_bim, ref_filepref + '_vars.dat')
        pca_stu_kwargs = {'U':U, 'dim_ref':dim_ref}

    if method == 'adp':
        saved_filesuffs = ['_mnsd.dat', '_XTX.dat', '_Vs.dat']
        saved_allexist = all([os.path.isfile(ref_filepref+suff) for suff in saved_filesuffs])
        X, X_bim, X_fam = read_bed(ref_filepref, dtype=np.float32)
        try:
            logging.info('Attemping to load saved reference PCA result...')
            X_mean, X_std = _load_mnsd(ref_filepref)
            XTX = np.loadtxt(ref_filepref+'_XTX.dat')[:, :dim_ref]
            standardize(X, X_mean, X_std)
            pcs_ref = _load_pcs_ref(ref_filepref)[:, :dim_ref]
            logging.info('Warning: If you have changed the parameter settings, please delete '
                         + ref_filepref + '_*.dat and ' + ref_filepref + '.pcs then rerun FRAPOSA.')
            logging.info('Reference PCA result loaded.')
        except OSError:
            logging.info('REFERENCE PCA result is either nonexistent or incomplete.')
            logging.info('Calculating REFERENCE PCA....')
            X_mean, X_std = standardize(X)
            s, V, XTX = eig_ref(X)
            V = V[:, :dim_ref]
            pcs_ref = V[:, :dim_ref] * s[:dim_ref]
            np.savetxt(ref_filepref+'_mnsd.dat', np.hstack((X_mean, X_std)), fmt=output_fmt)
            _write_pcs(pcs_ref, X_fam, colnames_pcs, ref_filepref, output_fmt)
            save_vars_bim(X_bim, ref_filepref + '_vars.dat')
        pca_stu_kwargs = {'pcs_ref':pcs_ref, 'XTX':XTX, 'X':X, 'dim_ref':dim_ref, 'dim_stu':dim_stu}

    if stu_filepref is not None:
        logging.info(datetime.now())
        logging.info('Loading study data...')
        W, W_bim, W_fam = read_bed(stu_filepref, dtype=np.int8, filt_iid=stu_filt_iid)

        # check to see that the variants are compatible between reference and study
        try:
            variants: Variants = compare_variants(ref_variants=X_bim, study_variants=W_bim)
        except NameError:
            with open(ref_filepref + '_vars.dat', 'r') as infile:
                ref_vars = infile.read().strip().split('\n')
            stu_vars = bim_varlist(W_bim)
            variants: Variants = compare_variants(ref_variants=ref_vars, study_variants=stu_vars)

        if variants.match_type == MatchType.DIFFERENT_ORDER:
            logging.info("Re-indexing variants and genotypes because study variant order was different to reference")
            W = W[variants.study_indexes, :]
            W_bim = W_bim.reindex(variants.study_variants)

        logging.info(datetime.now())
        logging.info('Predicting study PC scores (method: ' + method + ')...')
        t0 = time.time()
        pcs_stu = pca_stu(W, X_mean, X_std, method, **pca_stu_kwargs)
        elapse_stu = time.time() - t0

        # Write output
        _write_pcs(pcs_stu, W_fam, colnames_pcs, out_filepref, output_fmt, stage='STUDY')

        # Finish & Log
        logging.info('Study time: {} sec'.format(elapse_stu, 1))
        logging.info(datetime.now())
        logging.info('FRAPOSA finished.')


def pred_popu_stu(ref_filepref, stu_filepref, n_neighbors=20, weights='uniform'):
    # ToDo - test implementation
    # load reference and study pc scores and population
    ref_df = pd.read_table(ref_filepref+'.pcs', header=None)
    stu_df = pd.read_table(stu_filepref+'.pcs', header=None)
    popu_df = pd.read_table(ref_filepref+'.popu', header=None)
    pcs_ref = ref_df.iloc[:,2:].to_numpy()
    pcs_stu = stu_df.iloc[:,2:].to_numpy()
    popu_ref = popu_df.iloc[:,2:].to_numpy()
    n_stu, p = pcs_stu.shape

    popu_list = np.sort(np.unique(popu_ref))
    popu_dic = {popu_list[i] : i for i in range(len(popu_list))}
    knn = KNeighborsClassifier(n_neighbors=n_neighbors, weights=weights)
    knn.fit(pcs_ref, popu_ref)
    popu_stu_pred = knn.predict(pcs_stu)
    popu_stu_proba_list = knn.predict_proba(pcs_stu)
    popu_stu_proba = [popu_stu_proba_list[i, popu_dic[popu_stu_pred[i]]] for i in range(n_stu)]
    popu_stu_dist = knn.kneighbors(pcs_stu)[0][:,-1]
    popu_stu_dist = np.round(popu_stu_dist, 3)
    popuproba_df = pd.DataFrame({'popu':popu_stu_pred, 'proba':popu_stu_proba, 'dist':popu_stu_dist})
    popuproba_df = popuproba_df[['popu', 'proba', 'dist']]
    probalist_df = pd.DataFrame(popu_stu_proba_list)
    populist_df = pd.DataFrame(np.tile(popu_list, (n_stu, 1)))
    popu_stu_pred_df = pd.concat([stu_df.iloc[:,0:2], popuproba_df, probalist_df, populist_df], axis=1)
    popu_stu_pred_df.to_csv(stu_filepref+'.popu', sep='\t', header=False, index=False)
    print('Predicted study populations saved to ' + stu_filepref + '.popu')
    return popu_stu_pred, popu_stu_proba, popu_stu_dist


def plot_pcs(ref_filepref, stu_filepref):
    # ToDo - test implementation
    pcs_ref = np.loadtxt(ref_filepref+'.pcs', dtype=str)[:,2:].astype(float)
    pcs_stu = np.loadtxt(stu_filepref+'.pcs', dtype=str)[:,2:].astype(float)
    try:
        popu_ref = np.loadtxt(ref_filepref+'.popu', dtype=str)[:,2].tolist()
    except OSError:
        popu_ref = None
    try:
        popu_stu = np.loadtxt(stu_filepref+'.popu', dtype=str)[:,2].tolist()
    except OSError:
        popu_stu = None

    n_ref = pcs_ref.shape[0]
    n_stu = pcs_stu.shape[0]
    cmap = plt.get_cmap('tab10')
    legend_elements = []
    if popu_ref is None:
        color_ref = [cmap(0)] * n_ref
        color_stu = [cmap(1)] * n_stu
        legend_elements += [mpatches.Patch(facecolor=cmap(0), label='ref')]
        legend_elements += [mpatches.Patch(facecolor=cmap(1), label='stu')]
    else:
        popu_list = np.sort(np.unique(popu_ref))
        n_popu = len(popu_list)
        popu_dict = dict(zip(popu_list, range(n_popu)))
        color_ref = [cmap(popu_dict[e]) for e in popu_ref]
        if popu_stu is None:
            color_stu = ['xkcd:grey'] * n_stu
        else:
            color_stu = [cmap(popu_dict[e]) for e in popu_stu]
        legend_elements += [mpatches.Patch(facecolor=cmap(popu_dict[e]), label=e) for e in popu_list]
        legend_elements += [Line2D([0], [0], marker='o', color='white', label='ref', markerfacecolor='white', markeredgecolor='black')]
        legend_elements += [Line2D([0], [0], marker='s', color='white', label='stu', markerfacecolor='white', markeredgecolor='black')]
    plt.figure(figsize=(12, 6))
    for j in range(2):
        plt.subplot(1, 2, j+1)
        plt.scatter(pcs_ref[:, j*2], pcs_ref[:, j*2+1], marker='o', c=color_ref, alpha=0.1)
        plt.scatter(pcs_stu[:, j*2], pcs_stu[:, j*2+1], marker='s', c=color_stu, alpha=0.5, edgecolor='black', linewidths=2)
        plt.xlabel('PC' + str(j*2+1))
        plt.ylabel('PC' + str(j*2+2))
        plt.legend(handles=legend_elements)
    plt.savefig(stu_filepref+'.png', dpi=300)
    plt.close()
    print('PC plots saved to ' + stu_filepref+'.png')


# Code for bias-adjustment (method='AP')
# import rpy2.robjects as robjects
# from rpy2.robjects.packages import importr
# from rpy2.robjects import numpy2ri
# r = robjects.r
# robjects.numpy2ri.activate()
# importr('hdpca')
# hdpc_est = r['hdpc_est']

# def hdpca_shrinkage(s, p_ref, n_ref, dim_spikes=None, dim_spikes_max=16):
#     if dim_spikes is None:
#         hdpc_est_result  = hdpc_est(s**2, p_ref, n_ref, n_spikes_max=dim_spikes_max)
#     else:
#         hdpc_est_result  = hdpc_est(s**2, p_ref, n_ref, n_spikes=dim_spikes)
#     shrinkage = np.array(hdpc_est_result[-1])
#     return shrinkage