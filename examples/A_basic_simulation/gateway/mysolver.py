import numpy as np
from time import sleep


class mysolver():

    def __init__(self, method, nn):
        self.method = method
        self.size = nn
        self.mtx_A = np.zeros((nn,nn))
        self.inv_mtx = np.zeros((nn,nn))
        self.vec_b = np.zeros(nn)
        self.vec_x = np.zeros(nn)
        self.dbg = False

    def get_system_size(self):
        return self.size

    def set_method(self,method):
        self.method = method

    def get_method(self):
        return self.method

    def solve(self):
        if(self.method == 'gauss elimination'):
            return self.solve_gauss_elimination()
        else:
            return 1

    def set_bvec_elem(self,ii,value):
        self.vec_b[ii] = value
        if(self.dbg):
            print('set b[{}] = {}'.format(ii,value))
        #if(ii==0):
            #print('set b[{}] = {}'.format(ii,value))

    def add_bvec_elem(self,ii,value):
        self.vec_b[ii] = self.vec_b[ii] + value
        if(self.dbg):
            print('add to b[{}] + {} = {}'.format(ii,value,self.vec_b[ii]))
        #if(ii==0):
            #print('add to b[{}] + {} = {}'.format(ii,value,self.vec_b[ii]))

    def set_bvec(self,newvec):
        self.vec_b = newvec

    def reset_bvec(self):
        self.vec_b = np.zeros(self.size)

    def get_bvec(self):
        return self.vec_b

    def set_amtx_elem(self,ii,jj,value):
        self.mtx_A[ii,jj] = value
        if(self.dbg):
            print('set A[{},{}] = {}'.format(ii,jj,value))

    def add_amtx_elem(self,ii,jj,value):
        self.mtx_A[ii,jj] = self.mtx_A[ii,jj] + value
        if(self.dbg):
            print('add to A[{},{}] + {} = {}'.format(ii,jj,value,self.mtx_A[ii,jj]))

    def set_amtx(self,newmtx):
        self.mtx_A = newmtx

    def reset_amtx(self):
        self.mtx_A = np.zeros((self.size,self.size))

    def get_amtx(self):
        return self.mtx_A

    def print_solver(self):
        print(' A | C - b ')
        for ii in range(self.size):
            for jj in range(self.size):
                print('{:8.2f} '.format(self.mtx_A[ii,jj]), end = '', flush = True)
            print(' | ', end = '', flush = True)
            for jj in range(self.size):
                print('{:8.2f} '.format(self.inv_mtx[ii,jj]), end = '', flush = True)
            print(' - ', end = '', flush = True)
            print(' {:8.2f} '.format(self.vec_b[ii]))

    def print_system(self):
        print(' A * b = x')
        for ii in range(self.size):
            for jj in range(self.size):
                print('{:8.2f} '.format(self.mtx_A[ii,jj]), end = '', flush = True)
            print(' x ', end = '', flush = True)
            print(' {:8.2f} '.format(self.vec_x[ii]), end = '', flush = True)
            print(' = ', end = '', flush = True)
            print(' {:8.2f} '.format(self.vec_b[ii]))
                
    def print_sys_into_file(self, path):
        F = open(path,"w")
        F.write(' A * b = x\n')
        for ii in range(self.size):
            lin1 = ' '
            for jj in range(self.size):
                lin1 = lin1 + str('{:10.5f} '.format(self.mtx_A[ii,jj]))
            lin1 = lin1 + ' x '
            lin1 = lin1 + str(' {:10.5f} '.format(self.vec_x[ii]))
            lin1 = lin1 + ' = '
            lin1 = lin1 + str(' {:10.5f} \n'.format(self.vec_b[ii]))
            F.write(lin1)
        F.close()
                
    def print_solution(self):
        print(' A-1 * x = b')
        for ii in range(self.size):
            for jj in range(self.size):
                print('{:8.2f} '.format(self.inv_mtx[ii,jj]), end = '', flush = True)
            print(' x ', end = '', flush = True)
            print(' {:8.2f} '.format(self.vec_b[ii]), end = '', flush = True)
            print(' = ', end = '', flush = True)
            print(' {:8.2f} '.format(self.vec_x[ii]))
                

    def solve_gauss_elimination(self):
        #self.print_sys_into_file('./eqsys.dat')
        #print('sleep(20)')
        #sleep(20)
        errs = 0.00001
        self.inv_mtx = np.zeros((self.size, self.size))
        aa = np.zeros((self.size, self.size))
        for ii in range(self.size):
            self.inv_mtx[ii,ii] = 1.0
        aa = self.mtx_A
        bvec = self.vec_b
        for ii in range(self.size):
            #print('----------')
            #self.print_solver()
            wert = aa[ii,ii]
            kk = ii + 1
            while (abs(wert)<errs):
                if(kk >= self.size):
                    print('ERROR in gauss solver')
                aa = self.switch_mtx_zeilen(aa, ii, kk)
                self.inv_mtx = self.switch_mtx_zeilen(self.inv_mtx, ii, kk)
                bvec = self.switch_vec_zeilen(bvec, ii, kk)
                #wert = aa[ii,ii]
                kk = kk + 1

            for kk in range(self.size):
                aa[ii,kk] = aa[ii,kk] / wert
                self.inv_mtx[ii,kk] = self.inv_mtx[ii,kk] / wert
            if((ii +1) <= (self.size - 1)):
                for kk in range(self.size):
                    if (kk >= (ii+1)):
                        wert = aa[kk,ii]
                        if(abs(wert)>errs):
                            for jj in range(self.size):
                                aa[kk,jj] = aa[kk,jj] / wert - aa[ii,jj]
                                self.inv_mtx[kk,jj] = self.inv_mtx[kk,jj] / wert - self.inv_mtx[ii,jj]

        #print('----------')
        #self.print_solver()

        for ll in range(self.size):
            ii = self.size - 1 - ll
            wert = aa[ii,ii]
            for jj in range(self.size):
                aa[ii,jj] = aa[ii,jj] / wert
                self.inv_mtx[ii,jj] = self.inv_mtx[ii,jj] / wert
            #print('++++++++++')
            #self.print_solver()
            #print('wert = {}, ii = {}'.format(wert,ii))
            if(ii>=0):
                for nn in range(self.size):
                    kk = self.size - 1 - nn
                    if (kk <= (ii-1)):
                        wert = aa[kk,ii]
                        #print(' ii = {}; kk = {}, wert = {}'.format(ii,kk,wert))
                        if(abs(wert)>errs):
                            for jj in range(self.size):
                                #print(' < a[{},{}] = {} > / < wert = {} > - < a[{},{}] = {} >'.format(kk,jj,aa[kk,jj],wert,ii,jj,aa[ii,jj]))
                                aa[kk,jj] = aa[kk,jj] / wert - aa[ii,jj]
                                self.inv_mtx[kk,jj] = self.inv_mtx[kk,jj] / wert - self.inv_mtx[ii,jj]

        wyn = []
        self.vec_x = np.zeros(self.size)
        for ii in range(self.size):
            myv = 0.0
            for jj in range(self.size):
                myv = myv + self.inv_mtx[ii,jj] * bvec[jj]
            self.vec_x[ii] = myv 
            wyn.append(myv)

        #print('\n****************\n')
        return wyn
#
        def switch_vec_zeilen(self, vec, n1, n2):
            wert = vec[n1]
            vec[n1] = vec[n2]
            vec[n2] = wert
            return vec

        def switch_mtx_zeilen(self, mtx, n1, n2, nn):
            for jj in range(nn):
                wert = mtx[n1, jj]
                mtx[n1,jj] = mtx[n2,j]
                mtx[n2,jj] = wert
            return mtx
            
            