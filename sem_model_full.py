import numpy as np
from sem_percer import SEMParser
from scipy.stats import linregress
from pandas import read_csv
from sys import stdout
import itertools as it
from enum import Enum
import os


class SEMmx:
    BETA = 'Beta'
    GAMMA = 'Gamma'
    PI = 'Pi'
    LAMBDA = 'Lambda'
    KAPPA = 'Kappa'
    PHI_XI = 'Phi_xi'
    PHI_Y = 'Phi_y'
    THETA_DELTA = 'Theta_delta'
    THETA_EPS = 'Theta_eps'
    LAMBDA_U_ETA = 'Lambda_u_eta'
    LAMBDA_U_XI = 'Lambda_u_xi'
    LAMBDA_V_ETA = 'Lambda_v_eta'
    LAMBDA_V_XI = 'Lambda_v_xi'
    LAMBDA_PARTS = [LAMBDA_U_ETA, LAMBDA_U_XI, LAMBDA_V_ETA, LAMBDA_V_XI]
    KAPPA_U = 'Kappa_u'
    KAPPA_V = 'Kappa_v'
    KAPPA_PARTS = [KAPPA_U, KAPPA_V]
    SPART = 'Struct_Part'
    MPART = 'Measur_Part'
    SPART_COMB = [BETA, GAMMA, PI]  # Matrices in Structural Part
    MPART_COMB = [LAMBDA, KAPPA]  # Matrices in Measurement Part
    MX_COMB = [SPART, MPART]
    SYMMETRIC = [PHI_XI, PHI_Y, THETA_DELTA, THETA_EPS]  # SYMMETRIC MATRICES
    SIGMA_ETA = 'Sigma_eta'
    SIGMA_OMEGA = 'Sigma_omega'
    SIGMA_Z = 'Sigma_z'
    SIGMA_X = 'Sigma_x'
    SIGMAS = [SIGMA_ETA, SIGMA_Z, SIGMA_OMEGA, SIGMA_X]




class SEMModelFull:

    def __init__(self, file_model):

        # TODO assert
        model_descr = None
        with open(file_model, 'r') as f:
            model_descr = f.read()
        # TODO add asserts for model_descr

        sem_parser = SEMParser()
        self.sem_op = sem_parser.operations

        # REMOVE
        # sem_op = sem_parser.operations
        # model = sem_parser.parse(model_descr)
        # d_vars = SEMModel.classify_vars(model, sem_op)

        self.model = sem_parser.parse(model_descr)
        self.d_vars = self.classify_vars(self.model, self.sem_op)

        # Set matrices and parameters
        self.n_param = 0
        self.param_pos = []
        self.param_val = []  # initial values of parameters

        self.matrices = dict()

        # Get Matrices of path coefficients
        self.matrices[SEMmx.BETA] = self.set_beta()
        self.matrices[SEMmx.GAMMA] = self.set_gamma()
        self.matrices[SEMmx.KAPPA] = self.set_kappa()
        self.matrices[SEMmx.PI] = self.set_pi()
        self.matrices[SEMmx.LAMBDA] = self.set_lambda()

        # Get Symmetric Matrices of covariances
        self.matrices[SEMmx.THETA_DELTA] = self.set_theta_delta()
        self.matrices[SEMmx.THETA_EPS] = self.set_theta_eps()
        self.matrices[SEMmx.PHI_XI] = self.set_phi_xi()
        self.matrices[SEMmx.PHI_Y] = self.set_phi_y()

        # Create Blocks of Matrices
        self.matrices.update(self.set_lambda_parts())
        self.matrices.update(self.set_kappa_parts())

        # Create Combined Matrices
        self.matrices[SEMmx.SPART] = \
            self.set_mx_combined(SEMmx.SPART_COMB)
        self.matrices[SEMmx.MPART] = \
            self.set_mx_combined(SEMmx.MPART_COMB)




    # # TODO
    # def get_params_from_matrices():
    #     params = np.zeros(self.n_params)
    #     matrices = (self.m_beta, self.m_lambda, self.m_theta, self.m_psi)
    #     for mx, positions in matrices:
    #         for i, pos in positions.items():
    #             params[i] = mx[pos[0][0], pos[0][1]]
    #     return params

    @staticmethod
    def classify_vars(model, sem_op):
        """

        ANNA: variable are classified into categories:
        ObsBin - SNPs variables, observed exogenous in Structural part
        ObsNorm - Phenotype variables which are normally distributed
        ObsOrd - Phenotype variables which are categorical but ordered

        LatEndo - Latent Endogenous variables
        LatExo - Latent Exogenous variables
        LatBin - Latent variables introduced for ObsBin
        LatOrd - Laten variables introduced for ObaOrd
        LatOutput - Latent Variables which are fully output

        :param model:
        :param sem_op:
        :return:
        """

        vars_all = {v for v in model}

        # Latent variables
        vars_lat = {v for v in vars_all if model[v][sem_op.MEASUREMENT]}
        # Manifest variables
        vars_menif = {v for latent in vars_lat for v in model[latent][sem_op.MEASUREMENT]}
        # Onserved variables
        vars_obs = vars_all - vars_lat - vars_menif
        # Binary variables
        vars_bin = {v for v in vars_all
                    if model[v][sem_op.TYPE] and
                       ('binary' in model[v][sem_op.TYPE])}

        # Ordered variables
        vars_ord = {v for v in vars_all
                    if model[v][sem_op.TYPE] and
                    ('ordinal' in model[v][sem_op.TYPE])}

        # Endogenous variables
        vars_endo = {v for v in vars_all if model[v][sem_op.REGRESSION]}
        # Exogeneous
        vars_exo = (vars_lat | vars_obs) - vars_endo

        vars_upstream = {}
        for v in vars_all:
            if model[v][sem_op.REGRESSION]:
                vars_upstream |= model[v][sem_op.REGRESSION].keys()
        vars_output = vars_endo - vars_upstream - vars_ord

        # Create the dictionary
        acc = {}
        acc['ObsNorm'] = sorted(list((vars_obs | vars_menif) - vars_bin -
                                      vars_ord))
        acc['ObsBin'] = sorted(list(vars_bin))
        acc['ObsOrd'] = sorted(list(vars_ord))

        acc['LatExo'] = sorted(list(vars_lat & vars_exo))
        acc['LatEndo'] = sorted(list(vars_lat & vars_endo))
        acc['LatBin'] = ['_' + v for v in acc['ObsBin']]
        acc['LatOrd'] = ['_' + v for v in acc['ObsOrd']]

        acc['LatOutput'] = list(vars_output)

        # DO NOT SORT AGAIN
        acc['Lat'] = acc['LatExo'] + acc['LatEndo']
        acc['FirstManif'] = {latent:[*model[latent][sem_op.MEASUREMENT]][0] for latent in acc['Lat']}
        acc['Manif'] = acc['ObsNorm'] + acc['ObsOrd']


        # Symbols in the model
        acc['eta'] = acc['LatEndo']
        acc['xi'] = acc['LatExo']

        acc['g'] = acc['ObsBin']
        acc['y'] = acc['LatBin']

        acc['u'] = acc['ObsNorm']
        acc['v'] = acc['ObsOrd']
        acc['z'] = acc['LatOrd']

        # Dictionaries of symbols
        acc['d_eta'] = {v: i for i, v in enumerate(acc['eta'])}
        acc['d_xi'] = {v: i for i, v in enumerate(acc['xi'])}

        acc['d_g'] = {v: i for i, v in enumerate(acc['g'])}
        acc['d_y'] = {v: i for i, v in enumerate(acc['y'])}

        acc['d_u'] = {v: i for i, v in enumerate(acc['u'])}
        acc['d_v'] = {v: i for i, v in enumerate(acc['v'])}
        acc['d_z'] = {v: i for i, v in enumerate(acc['z'])}

        acc['x'] = acc['u'] + acc['v']
        acc['d_x'] = {v: i for i, v in enumerate(acc['x'])}

        acc['omega'] = acc['eta'] + acc['xi']
        acc['d_omega'] = {v: i for i, v in enumerate(acc['omega'])}
        acc['d_first_manif'] = {latent: [*model[latent][sem_op.MEASUREMENT]][0]
                              for
                             latent in acc['Lat']}

        return acc

    def add_parameter(self, param_type, pos1, pos2, param_id = None):
        """
        Add new parameters
        :param param_type:
        :param pos1:
        :param pos2:
        :return:
        """
        if param_id is None:
            param_id = self.n_param
            self.n_param += 1
            self.param_val.append(0)

        self.param_pos += (param_type, pos1, pos2, param_id)

    def set_beta(self):
        """
        Funtion to set Beta matrix
        Size of Beta is LatEndo:LatEndo
        :return: Beta matrix
        """

        # ExoLat variables in structural part of SEM (eta)
        v_eta = self.d_vars['eta']
        d_eta = self.d_vars['d_eta']

        # create Beta matrix with indicators of parameters
        n_eta = len(v_eta)
        m_beta = np.zeros((n_eta, n_eta))

        for v1, v2 in it.permutations(v_eta, 2):
            if v2 in self.model[v1][self.sem_op.REGRESSION]:
                self.add_parameter('Beta', d_eta[v1], d_eta[v2])
        return m_beta

    def set_gamma(self):
        """
        Funtion to set Gamma matrix
        Size of Gamma is LatEndo:LatExo
        :return: Gamma matrix
        """

        # eta and xi variables in structural part of SEM
        v_eta = self.d_vars['eta']
        d_eta = self.d_vars['d_eta']
        v_xi = self.d_vars['xi']
        d_xi = self.d_vars['d_xi']

        # create Gamma matrix with indicators of parameters
        n_eta = len(v_eta)
        n_xi = len(v_xi)
        m_gamma = np.zeros((n_eta, n_xi))

        for v1, v2 in it.product(v_eta, v_xi):
            if v2 in self.model[v1][self.sem_op.REGRESSION]:
                self.add_parameter('Gamma', d_eta[v1], d_xi[v2])
        return m_gamma

    def set_pi(self):
        """
        Funtion to set Pi matrix
        Size of Pi is LatEndo:ObsBin
        :return: Pi matrix
        """
        # eta and g variables in structural part of SEM
        v_eta = self.d_vars['eta']
        d_eta = self.d_vars['d_eta']
        v_g = self.d_vars['g']
        d_g = self.d_vars['d_g']

        # create Pi matrix with indicators of parameters
        n_eta = len(v_eta)
        n_g = len(v_g)
        m_pi = np.zeros((n_eta, n_g))

        for v1, v2 in it.product(v_eta, v_g):
            if v2 in self.model[v1][self.sem_op.REGRESSION]:
                self.add_parameter('Pi', d_eta[v1], d_g[v2])
        return m_pi

    def set_lambda(self):
        """

        """
        # variables in structural part of SEM
        v_x = self.d_vars['x']
        d_x = self.d_vars['d_x']
        v_omega = self.d_vars['omega']
        d_omega = self.d_vars['d_omega']

        d_fisrt_manif = self.d_vars['d_first_manif']

        # create Lambda matrix with indicators of parameters
        n_x = len(v_x)
        n_omega = len(v_omega)
        m_lambda = np.zeros((n_x, n_omega))

        # Define fixed_to-one parameters and parameters for estimation
        for v2 in v_omega:
            for v1 in self.model[v2][self.sem_op.MEASUREMENT]:
                if v1 is d_fisrt_manif[v2]:  # for the first - set 1
                    m_lambda[d_x[v1], d_omega[v2]] = 1
                else:
                    self.add_parameter('Lambda', d_x[v1], d_omega[v2])

        return m_lambda

    def set_kappa(self):
        """
        Funtion to set Kappa matrix
        Size of Kappa is Manif:ObsBin
        :return: Kappa matrix
        """
        v_x = self.d_vars['x']
        d_x = self.d_vars['d_x']
        v_g = self.d_vars['g']
        d_g = self.d_vars['d_g']

        # create Pi matrix with indicators of parameters
        n_x = len(v_x)
        n_g = len(v_g)
        m_kappa = np.zeros((n_x, n_g))

        for v1, v2 in it.product(v_x, v_g):
            if v2 in self.model[v1][self.sem_op.REGRESSION]:
                self.add_parameter('Kappa', d_x[v1], d_g[v2])
        return m_kappa

    def set_theta_delta(self):
        """
        Covariance matrix of errors in measurement part
        not fully diagonal
        """

        v_eta = self.d_vars['eta']
        d_eta = self.d_vars['d_eta']

        v_output = self.d_vars['LatOutput']

        # create Beta matrix with indicators of parameters
        n_eta = len(v_eta)
        m_theta_delta = np.zeros((n_eta, n_eta))

        # Fill diagonal elements
        for v1 in v_eta:
            self.add_parameter('Theta_delta', d_eta[v1], d_eta[v1])

        # Fill covariances for output variables
        for v1, v2 in it.combinations(v_output, 2):
            self.add_parameter('Theta_delta', d_eta[v1], d_eta[v2])

        return m_theta_delta

    def set_theta_eps(self):
        """
        Covariance matrix of errors in measurement part
        only diagonal
        """

        v_x = self.d_vars['x']
        d_x = self.d_vars['d_x']

        n_x = len(v_x)
        m_theta_eps = np.zeros((n_x, n_x))
        for v in v_x:
            self.add_parameter('Theta_eps', d_x[v], d_x[v])

        return m_theta_eps

    def set_phi_xi(self):
        """
        Set covariance matrix for Exogenous Latent
        Size is LatExo:LatExo
        Full matrix, not diagonal
        :return:
        """

        v_xi = self.d_vars['xi']
        d_xi = self.d_vars['d_xi']

        # create Beta matrix with indicators of parameters
        n_xi = len(v_xi)
        m_phi_xi = np.zeros((n_xi, n_xi))

        for v1, v2 in it.combinations_with_replacement(v_xi, 2):
            self.add_parameter('Phi_xi', d_xi[v1], d_xi[v2])
        return m_phi_xi

    def set_phi_y(self):
        """

        :return:
        """

        v_g = self.d_vars['g']
        d_g = self.d_vars['d_g']

        # create Beta matrix with indicators of parameters
        n_g = len(v_g)
        m_phi_xi = np.zeros((n_g, n_g))

        for v1, v2 in it.combinations_with_replacement(v_g, 2):
            self.add_parameter('Phi_y', d_g[v1], d_g[v2])
        return m_phi_xi

    def set_mx_combined(self, mx_list):

        mx_combined = np.concatenate((self.matrices[mx] for mx in mx_list),
                                     axis=1)

        n_col_shift = {mx1: self.matrices[mx2].shape[1]
                       for mx1, mx2 in zip(mx_list[:-1], mx_list[1:])}

        for mx_type, pos1, pos2, param_id in self.param_pos:
            if mx_type not in mx_list:
                continue
            self.add_parameter(mx_type,
                               pos1, pos2 + n_col_shift[mx_type],
                               param_id)

        return mx_combined

    def set_lambda_parts(self):
        """

        :param params:
        :return:
        """
        v_u = self.d_vars['u']
        v_v = self.d_vars['v']
        v_eta = self.d_vars['eta']
        v_xi = self.d_vars['xi']

        d_x = self.d_vars['d_x']
        d_omega = self.d_vars['d_omega']

        mx_lambda = self.matrices[SEMmx.LAMBDA]
        lambda_params = [(pos1, pos2, param_id)
                         for mx_type, pos1, pos2, param_id in self.param_pos
                         if mx_type == SEMmx.LAMBDA]

        mx_lambda_parts = dict()

        for lambda_part in SEMmx.LAMBDA_PARTS:
            if lambda_part is SEMmx.LAMBDA_U_ETA:
                rows = [i for k, i in d_x if k in v_u]
                cols = [i for k, i in d_omega if k in v_eta]
            elif lambda_part is SEMmx.LAMBDA_V_ETA:
                rows = [i for k, i in d_x if k in v_v]
                cols = [i for k, i in d_omega if k in v_eta]
            elif lambda_part is SEMmx.LAMBDA_U_XI:
                rows = [i for k, i in d_x if k in v_u]
                cols = [i for k, i in d_omega if k in v_xi]
            elif lambda_part is SEMmx.LAMBDA_V_XI:
                rows = [i for k, i in d_x if k in v_v]
                cols = [i for k, i in d_omega if k in v_xi]
            else:
                raise ValueError('Invalid Matrix Name')

            # Create New Matrix. It is important to copy initial Lambda as
            # Lambda contains several 1-values for the first manifest variable
            mx_tmp = np.array(mx_lambda[rows, cols])
            # Add the new matrix to the set of all Matrices
            mx_lambda_parts[lambda_part] = mx_tmp

            # Add annotations of new parameters
            row_order = {row: i for i, row in enumerate(rows)}
            col_order = {col: i for i, col in enumerate(cols)}
            for pos1, pos2, param_id in lambda_params:
                if (pos1 in rows) and (pos2 in cols):
                    self.add_parameter(lambda_part,
                                       row_order[pos1],
                                       col_order[pos2], param_id)

        return mx_lambda_parts

    def set_kappa_parts(self):
        """

        :return:
        """
        v_u = self.d_vars['u']
        v_v = self.d_vars['v']

        d_x = self.d_vars['d_x']

        mx_kappa= self.matrices[SEMmx.KAPPA]
        kappa_params = [(pos1, pos2, param_id)
                        for mx_type, pos1, pos2, param_id in self.param_pos
                        if mx_type == SEMmx.LAMBDA]

        mx_kappa_parts = dict()
        for kappa_part in SEMmx.KAPPA_PARTS:
            if kappa_part is SEMmx.KAPPA_U:
                rows = [i for k, i in d_x if k in v_u]
            elif kappa_part is SEMmx.LAMBDA_V_ETA:
                rows = [i for k, i in d_x if k in v_v]

            else:
                raise ValueError('Invalid Matrix Name')

            # Create New Matrix. It is important to copy initial Kappa as
            # Kappa contains several 1-values for the first manifest variable
            mx_tmp = np.array(mx_kappa[rows, :])
            # Add the new matrix to the set of all Matrices
            mx_kappa_parts[kappa_part] = mx_tmp

            # Add annotations of new parameters
            row_order = {row: i for i, row in enumerate(rows)}
            for pos1, pos2, param_id in kappa_params:
                if pos1 in rows:
                    self.add_parameter(kappa_part,
                                       row_order[pos1], pos2, param_id)

        return mx_kappa_parts

    def get_matrix(self, params, mx_name):
        """
        Get Beta matrix with parameters from params
        :param params:
        :return:
        """

        # If matrix should be calculated
        if mx_name in SEMmx.SIGMAS:
            return self.get_sigma(params, mx_name)

        for mx_type, pos1, pos2, param_id in self.param_pos:
            if mx_type is not mx_name:
                continue
            self.matrices[mx_type][pos1, pos2] = params[param_id]
            if mx_type in SEMmx.SYMMETRIC:
                self.matrices[mx_type][pos2, pos1] = params[param_id]

        return self.matrices[mx_name]

    def get_sigma(self, params, mx_name):

        def get_sigma_eta(params):
            m_beta = self.get_matrix(params, SEMmx.BETA)
            m_gamma = self.get_matrix(params, SEMmx.GAMMA)
            m_pi = self.get_matrix(params, SEMmx.PI)
            m_phi_xi = self.get_matrix(params, SEMmx.PHI_XI)
            m_phi_y = self.get_matrix(params, SEMmx.PHI_Y)
            m_theta_delta = self.get_matrix(params, SEMmx.THETA_DELTA)

            m_c = np.linalg.pinv(np.identity(m_beta.shape[0]) - m_beta)

            return m_c @ (m_gamma @ m_phi_xi @ m_gamma.T +
                          m_pi @ m_phi_y @ m_pi.T +
                          m_theta_delta) @ m_c.T

        def get_sigma_omega(params):
            pass

        def get_sigma_x(params):
            pass

        def get_sigma_z(params):
            m_beta = self.get_matrix(params, SEMmx.BETA)
            m_gamma = self.get_matrix(params, SEMmx.GAMMA)
            m_pi = self.get_matrix(params,  SEMmx.PI)
            m_phi_xi = self.get_matrix(params, SEMmx.PHI_XI)
            m_phi_y = self.get_matrix(params, SEMmx.PHI_Y)
            m_theta_delta = self.get_matrix(params, SEMmx.THETA_DELTA)
            m_theta_eps = self.get_matrix(params, SEMmx.THETA_EPS)
            m_c = np.linalg.pinv(np.identity(m_beta.shape[0]) - m_beta)

            m_lambda_v_eta = self.get_matrix(params, SEMmx.LAMBDA_V_ETA)
            m_lambda_v_xi = self.get_matrix(params, SEMmx.LAMBDA_V_XI)
            m_kappa_v = self.get_matrix(params, SEMmx.KAPPA_V)

            m_a_xi = m_lambda_v_eta @ m_c @ m_gamma + m_lambda_v_xi
            m_a_g = m_lambda_v_eta @ m_c @ m_pi + m_kappa_v
            m_a_delta = m_lambda_v_eta @ m_c

            m_sigma_v = m_a_xi @ m_phi_xi @ m_a_xi.T + \
                        m_a_g @ m_phi_y @ m_a_g.T + \
                        m_a_delta @ m_theta_delta @ m_a_delta.T + \
                        m_theta_eps

            return m_sigma_v

        if mx_name == SEMmx.SIGMA_ETA:
            return get_sigma_eta(params)
        elif mx_name == SEMmx.SIGMA_OMEGA:
            return get_sigma_omega(params)
        elif mx_name == SEMmx.SIGMA_Z:
            return get_sigma_z(params)
        else:
            raise ValueError('Name of sigma-matrix is not correct')

    #
    # def update_all(self, params=None):
    #     """
    #     Set New parameters or Update matrixes from parameters
    #     :param params:
    #     :return:
    #     """
    #     # TODO LEN of parameters
    #     if params is not None:
    #         self.check_params(params)
    #         # self.param_val = params
    #     else:
    #         params = self.param_val
    #
    #     # ANNA print('updated', params)
    #     for i, position in self.param_pos.items():
    #         mx_type, pos1, pos2 = position
    #         if mx_type in {'Beta', 'Lambda'}:
    #             self.matrices[mx_type][pos1, pos2] = params[i]
    #         elif mx_type in {'Psi', 'Theta'}:  # Symmetric matrices
    #             self.matrices[mx_type][pos1, pos2] = params[i]
    #             self.matrices[mx_type][pos2, pos1] = params[i]
    #
    # def load_initial_dataset(self, data: SEMData):
    #     """
    #     Set Initial values into Matrices
    #     :param data:
    #     :return:
    #     """
    #
    #     # TODO check whether the dataset and the model are in agreement
    #
    #     m_cov = data.m_cov
    #     m_profiles = data.m_profiles
    #     d_spart = self.d_vars['D_SPart']
    #     d_mpart = self.d_vars['D_MPart']
    #     v_spart = self.d_vars['SPart']
    #     v_mpart = self.d_vars['MPart']
    #     v_obsexo = self.d_vars['ObsExo']
    #     v_lat = self.d_vars['Lat']
    #     d_first_manif = self.d_vars['D_First_Manif']
    #
    #     # Matrix Beta - regression coefficients
    #     for i, position in self.param_pos.items():
    #         mx_type, pos1, pos2 = position
    #         if mx_type != 'Beta':
    #             continue
    #
    #         # if v_spart[pos1] in v_lat:
    #         #     profile1 = m_profiles[:, d_mpart[d_first_manif[v_spart[pos1]]]]
    #         # else:
    #         #     profile1 = m_profiles[:, d_mpart[v_spart[pos1]]]
    #         #
    #         # if v_spart[pos2] in v_lat:
    #         #     profile2 = m_profiles[:, d_mpart[d_first_manif[v_spart[pos2]]]]
    #         # else:
    #         #     profile2 = m_profiles[:, d_mpart[v_spart[pos2]]]
    #
    #         # lin_reg = linregress(profile2, profile1)
    #         # self.param_val[i] = lin_reg.slope
    #         self.param_val[i] = 0
    #
    #     # Matrix Lambda - regression coefficients
    #     # first pos1 from MPart
    #     # second pos2 - from SPart
    #     for i, position in self.param_pos.items():
    #         mx_type, pos1, pos2 = position
    #         if mx_type != 'Lambda':
    #             continue
    #
    #         # first - is measured
    #         profile1 = m_profiles[:, pos1]
    #         # second is always latent
    #         profile2 = m_profiles[:, d_mpart[d_first_manif[v_spart[pos2]]]]
    #
    #         lin_reg = linregress(profile2, profile1)
    #         self.param_val[i] = lin_reg.slope
    #
    #     # Matrix Psi - covariances from structural part not for latent variables
    #     for i, position in self.param_pos.items():
    #         mx_type, pos1, pos2 = position
    #         if mx_type != 'Psi':
    #             continue
    #
    #         if pos1 != pos2:
    #             continue
    #
    #         if v_spart[pos1] in v_lat:
    #             self.param_val[i] = 0.05
    #             continue
    #
    #         # Translation from structural part into measurement
    #         pos1 = pos2 = d_mpart[v_spart[pos1]]
    #
    #         # only diagonal variance
    #         self.param_val[i] = m_cov[pos1][pos2] / 2
    #
    #
    #
    #     # Matrix Theta - covariances from measurement part
    #     for i, position in self.param_pos.items():
    #         mx_type, pos1, pos2 = position
    #         if mx_type != 'Theta':
    #             continue
    #         self.param_val[i] = m_cov[pos1][pos2] / 2
    #
    #     # Psi matrix :  set fixed variances for exogenous observed variables
    #     for v1, v2 in it.product(v_obsexo, repeat=2):  # all symmetric variants
    #         pos1 = d_spart[v1]
    #         pos2 = d_spart[v2]
    #
    #         # Translation from structural part into measurement
    #         pos_cov1 = d_mpart[v1]
    #         pos_cov2 = d_mpart[v2]
    #
    #         self.matrices['Psi'][pos1, pos2] = m_cov[pos_cov1, pos_cov2]
    #
    #     # DO NOT Update matrices
    #
    # def get_matrices(self, params=None, mx_type='All'):
    #     """
    #     Matrices are updated by default
    #     :param params:
    #     :return:
    #     """
    #     if params is not None:
    #         self.check_params(params)
    #
    #     self.update_all(params)
    #
    #
    #     # The returned matrices are updated
    #     if mx_type is 'All':
    #         return self.matrices
    #     if mx_type in self.matrices.keys():
    #         return self.matrices[mx_type]
    #
    # def get_bounds(self):
    #     mx_to_fix = ['Theta', 'Psi']
    #     bounds = []
    #     for i, position in self.param_pos.items():
    #         mx_type, pos1, pos2 = position
    #         if mx_type in mx_to_fix:
    #             bounds.append((0, None))
    #         else:
    #             bounds.append((None, None))
    #     return bounds
    #
    # def check_params(self, params):
    #     """
    #     Chechs parameters
    #     :param params:
    #     :return:
    #     """
    #     if len(params) != self.n_param:
    #         print(len(params), self.n_param)
    #         raise ValueError('Length of parameters is not valid')
    #     if not all(isinstance(p, (int, float)) for p in params):
    #         raise ValueError('Invalid values')
    #
    # def check_covariances(self, output=stdout):
    #     """
    #     Checks matricies' values to be A-OK.
    #     :param output:
    #     :return:
    #     """
    #     if np.any(np.diag(self.m_theta[0]) < 0) or np.any(np.diag(self.m_psi[0]) < 0):
    #         print("Warning: some of variances are negative.", file=output)
    #         raise ValueError("Warning: some of variances are negative.")
    #     if np.any(np.linalg.eigvals(self.m_theta[0]) < 0):
    #         print("Warning: theta matrix is not positive definite.", file=output)
    #         raise ValueError("Warning: theta matrix is not positive definite")
    #     if np.any(np.linalg.eigvals(self.m_psi[0]) < 0):
    #         print("Warning: psi matrix is not positive definite.", file=output)
    #         raise ValueError("Warning: psi matrix is not positive definite.")