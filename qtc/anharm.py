import os
import sys
import numpy as np

from . import iotools as io
from . import qctools as qc
import logging
def gauss_xmat(filename,natoms):
    """
    Retrieves the anharmonic constant matrix from Gaussian logfile 
    INPUTS:
    filename - name of gaussian logfile
    natoms   - number of atoms in molecule
    OUTPUT:
    xmat     - anharmonic constant matrix (nmode by nmode)
    """ 
    full = io.read_file(filename)
    nmodes = 3*natoms-6 
    lines = full.split('X matrix')[1].split('Resonance')[0]
    lines = lines.split('\n')
    del lines[0]
    del lines[-1]
    
    xmat = np.zeros((nmodes, nmodes))
    rangemod = 1
    if nmodes%5 == 0:
       rangemod = 0
    marker = 0

    for m in range(0,nmodes/5+rangemod):
        length = nmodes - m * 5 
        a= np.array( lines[marker+1:marker+length+1])
        for i in range(length):
            for j in range(0,len(a[i].split())-1):
                xmat[m*5 + i,m*5 + j] = a[i].split()[j+1]
                xmat[m*5 + j,m*5 + i] = a[i].split()[j+1]
        marker += length+1

    return xmat


def get_freqs(filename):
    """
    Pulls the frequencies out from EStokTP me output file 
    INPUT:
    filename - name of EStokTP output file (reac1_fr.me or reac1_unpfr.me)
    OUTPUT:
    freqs    - frequencies obtained from output file
    order    - in case the frequencies were reordered when sorting, keeps 
               track of which index of freqs corresponds to which normal mode
    """ 
    full = io.read_file(filename)
    full = full.strip('\n')
    full = full.split('[1/cm]')[1].split('Zero')[0] 
    full = full.split('ElectronicLevels')[0] 
    full = full.split('End')[0] 
    full = full.split()
    nfreqs = full[0]
    freqs = full[1:]
    if 'ts' in filename:
        imaginary = io.read_file(filename)
        imaginary=imaginary.split('ImaginaryFrequency[1/cm]')[1].split()[0]
        freqs.insert(0,'-' + imaginary)
    #[freq=float(freq) for freq in freqs]
    freqs = np.array(map(float, freqs))
    a= freqs.argsort()
    freqs = np.sort(freqs)
    return freqs.tolist(), a.tolist()


def find_hinfreqs(proj,unproj,order):
    """
    Compares the frequencies from EStokTP projected and unprojected frequency
    output to determine which normal modes are hindered rotors
    INPUTS:
    proj   -  frequencies after projection
    unproj -  unprojected frequencies
    order  -  in case the frequencies were reordered when sorting, keeps track of 
              which index of unproj corresponds to which normal mode
    """
    diff = len(unproj) - len(proj)
    if diff > 0:
        for i in range(len(proj)):
            length = len(unproj)-1
            closeenough = 0.02
            for k in range(len(unproj)):
                if (abs(proj[i]-unproj[k]) < unproj[k] * closeenough):
                    #proj = np.delete(proj, 0)
                    unproj = np.delete(unproj, k)
                    order = np.delete(order, k)
                    break
        order = order[:diff]
    else:
        order = []
    modes = [mode+1 for mode in order]
    return modes

def remove_modes(xmat,modes):
    """
    Removes specified modes from anharmonic constant matrix
    INPUTS:
    xmat  - anharmonic constant matrix
    m?odes - the modes to delete from the matrix (with 1 being the first mode)
    OUTPUTS:
    xmat  - anharmonic constant matrix with columns and rows deleted for specified modes
    """
    modes.sort()#reverse=True)
    modeindex = [mode-1 for mode in modes]
    for index in modeindex[::-1]:
        xmat = np.delete(xmat,index,0)
        xmat = np.delete(xmat,index,1)
    return xmat

def remove_vibrots(vibrot,modes):
    """
    Removes specified modes from anharmonic constant matrix
    INPUTS:
    xmat  - anharmonic constant matrix
    modes - the modes to delete from the matrix (with 1 being the first mode)
    OUTPUTS:
    xmat  - anharmonic constant matrix with columns and rows deleted for specified modes
    """
    modes.sort()#reverse=True)
    vibrot = vibrot.splitlines()
    modeindex = [mode-1 for mode in modes]
    vibrots = []
    for index in range(len(vibrot)):
        if index not in modeindex:
            vibrots.append(vibrot[index])
    return '\n'.join(vibrots)

def gauss_anharm_inp(filename,anlevel):
    """
    Forms the Gaussian input file for anharmonic frequency computation following an EStokTP 
    level 1 computation on a molecule
    INPUT:
    filename - EStokTP output file to read (reac1_l1.log)
    OUTPUT:
    zmat     - lines for entire guassian input file (not just the zmat part, its poorly named)
    """
    full = io.read_file(filename)
    full = full.split('Z-matrix:')
    zmat = full[0].split('***************************')[2].replace('*','')
    zmat = zmat.split('Will')[0]
    zmat = ' ' + zmat.lstrip()
    zmat += full[0].split('-------------------------------------------')[3].replace('-','').replace('-','').replace('-','').replace('\n ','')
    if not anlevel == 'ignore':
        if 'ts' in filename:
            zmat =  zmat.split('#')[0] + ' # ' + anlevel + ' opt=(ts,calcfc,noeig,internal,maxcyc=50)' + zmat.split('#')[2]
        else:
            zmat =  zmat.split('#')[0] + ' # ' + anlevel + ' opt=(internal)' + zmat.split('#')[2]
    zmat = zmat.replace('freq','freq=(anharm,vibrot,readanharm)')
    zmat += '\n\nAnharmonic computation\n'
    zmat += full[1].split('       Variables:')[0]
    zmat += 'Variables:\n'
    zmat = zmat.replace('Charge = ','')
    zmat = zmat.replace('Multiplicity =','')
    try:
       varis = full[1].split('Optimized Parameters')[1].split('--------------------------------------')[1]
       varis = varis.split('\n')
    except:
       varis = [0,0]
    del varis[0]
    del varis[-1]
    for var in varis:
        var = var.split()
        zmat += ' '+  var[1] + '\t' + var[2] + '\n'
    zmat += '\nPrint=NMOrder=AscNoIrrep\n\n'
    return zmat

def write_anharm_inp(readfile='reac1_l1.log',writefile='anharm.inp',anlevel='ignore'):
    
    """
    Writes Guassian input to a file given an EStokTP G09 output file name
    INPUT:
    readfile  - EStokTP output file to read (reac1_l1.log)
    writefile - name of Gaussian input file to write
    """
    zmat = gauss_anharm_inp(readfile,anlevel)
    io.write_file(zmat,writefile)
    return

def run_gauss(filename,node):
    """
    Executes Guassian 
    INPUT:
    filename - name of Guassian input file
    node     - node to run it on
    """
    if io.check_file(filename):
        executea = 'soft add +gcc-5.3; soft add +g09-e.01; g09 ' + filename 
        executeb = 'cd `pwd`; export PATH=$PATH:~/bin; '
        ssh ='/usr/bin/ssh'
        host =node
        if str(host) == '0':
            os.system(executea)
        else: 
            os.system('exec ' + ssh + ' -n ' + host +' \"' + executeb + executea + '\"')
    
    return

def anharm_freq(freqs,xmat):
    """
    Uses anharmonic frequency matrix and harmonic frequencies to compute VPT2 anharmonic frequencies
    INPUT:
    freqs   - harmonic frequencies
    xmat    - anharmonic constant matrix
    OUTPUT:
    anharms - VPT2 anharmonic frequencies
    """
    anharms = np.zeros(len(freqs))
    for i, freq in enumerate(freqs):
        anharms[i]  = freq
        anharms[i] += 2. * xmat[i][i]
        tmp = 0
        for j in range(len(freqs)):
            if j != i:
                tmp += xmat[i][j]
        if tmp > 0:
            logging.warning('Positive anharmonic correction on Mode {:d}'.format(i+1))
        if tmp < 400:
            logging.warning('Large anharmonic correction of {:f} on Mode {:d}'.format(tmp, i+1))
        anharms[i] += 1./2 * tmp

    return anharms

def mess_x(xmat, anfreq=[]):
    inp = ''
    removefirst = 0
    if len(anfreq)>0:
       if anfreq[0] < 0:
           removefirst = 1
    if len(xmat) > 0:
        inp = ' Anharmonicities[1/cm]\n'
        for i in range( len(xmat)-removefirst):
            for j in range(i+1):
                 inp += '   {:.3f}'.format(xmat[i+removefirst][j+removefirst])
            inp += '\n'
        inp += ' End\n'
    return inp

def mess_fr(freqs):

    n = 0
    if freqs[0] < 0:
        n = 1
    inp = '    Frequencies[1/cm]           ' + str(len(freqs)-n) + '\n     '
    for i, freq in enumerate(freqs[n:]):
       inp += '%4.1f\t'%freq
       if (i+1)%10 == 0:
           inp += '\n     '
    inp += '\n'
    return inp

def main(args, vibrots = None):
    
    extra = ' ZeroEnergy[kcal/mol]\t 0.\n ElectronicLevels[1/cm]\t\t1\n  0.0000000000000000\t\t1.0000000000000000\nEnd'
    getextra = False
    if isinstance(args, dict):
        #natoms    = args['natoms']
        if 'writegauss' in args:
            if args['writegauss'] == 'true':
                anharminp = args['anharmlog' ] + '.inp'
                anlevel = args['anlevel'].replace('g09','gaussian')
                write_anharm_inp(args['logfile'],anharminp,'{}/{}'.format(anlevel.split('/')[1], anlevel.split('/')[2]))
        if 'rungauss' in args:
            if args['rungauss'] == 'true':
                anharminp = args['anharmlog' ] + '.inp'
                node = args['node' ]
                run_gauss(anharminp,node)
        if 'pfreqs' in args:
            proj = np.array(args['pfreqs']).astype(np.float)
            unproj = np.array(args['freqs']).astype(np.float)
            proj = np.sort(proj)
            unproj = np.sort(unproj)
            a = np.arange(len(proj)+1)
            b = np.arange(len(unproj)+1)
            #a = nargs['pfreqs']).argsort()[::-1]
            #b = args['freqs'].argsort()[::-1]
        else:
            proj, a   = get_freqs(args['freqfile'])
            unproj, b = get_freqs(args['unprojfreq'])
        if 'ts' in args['freqfile']:
            getextra = True
        #xmat = gauss_xmat(anharmlog,natoms)
        if 'xmat' in args:
            xmat = args['xmat']
        else:
            smiles    = args['smiles']
            anlevel   = args['theory' ]
            optlevel  = args['optlevel']
            anharmlog = args['anharmlog' ] + '.log'
            #try:
            #    andire = io.db_sp_path(anlevel.split('/')[0], anlevel.split('/')[1], anlevel.split('/')[2], None, smiles,
            #          optlevel[0], optlevel[1], optlevel[2])
            #except:
            #    andire = ''
            #if io.check_file(andire + '/' + smiles + '.xmat'):
            #    xmat = io.db_get_sp_prop(smiles, 'xmat', andire).split('\n')
            #    for i in range(len(xmat)):
            #        xmat[i] = xmat[i].split(',')
            if io.check_file(anharmlog):
                xmat = qc.get_gaussian_xmatrix(io.read_file(anharmlog),len(unproj))
        modes     = find_hinfreqs(proj,unproj,b)
        if type(xmat) == list:
            for i in range(len(xmat)):
                xmat[i][i] = float(xmat[i][i])
                for j in range(i):
                    xmat[i][j] = float(xmat[i][j])
                    xmat[j][i] = xmat[i][j]
            xmat      = remove_modes(xmat,modes)
            anfreq = anharm_freq(proj,xmat)
        else:
            xmat = []
            anfreq = proj
        #proj, b   = get_freqs(eskproj)
        if vibrots:
            vibrots = remove_vibrots(vibrots, modes)
        if getextra:
            extra +=   '\t\tTunneling    Eckart\n\tImaginaryFrequency[1/cm]\t{}\n\tWellDepth[kcal/mol]\t$wdepfor\n\tWellDepth[kcal/mol]\t$wdepback\nEnd'.format(abs(anfreq[0]))
        return anfreq, mess_fr(anfreq),  xmat, mess_x(xmat,anfreq), extra, vibrots
    ##########################
    else: 
        anharmlog = args.anharmlog
        natoms    = args.natoms
        eskfile   = args.logfile
        eskproj   = args.freqfile
        eskunproj = args.unprojfreq
        anharmlog = args.anharmlog
        node      = args.node
        if 'ts' in args.freqfile:
            getextra = True
        if args.writegauss.lower() == 'true':
            write_anharm_inp(eskfile,'anharm.inp')
        if args.rungauss.lower() == 'true':
            run_gauss('anharm.inp',node)
        if args.computeanharm.lower() == 'true':
            xmat = gauss_xmat(anharmlog,natoms)
            proj, b   = get_freqs(eskproj)
            unproj, a = get_freqs(eskunproj)
            modes     = find_hinfreqs(proj,unproj,a)
            xmat      = remove_modes(xmat,modes)
            proj, b   = get_freqs(eskproj)
            anfreq = anharm_freq(proj,xmat)
            if getextra:
                extra +=   '\t\tTunneling    Eckart\n\tImaginaryFrequency[1/cm]\t{}\n\tWellDepth[kcal/mol]\t$wdepfor\n\tWellDepth[kcal/mol]\t$wdepback\nEnd'.format(abs(anfreq[0]))
            return anfreq, mess_fr(anfreq), xmat, mess_x(xmat,anfreq), extra, vibrots
    return 

if __name__ == '__main__':

    #SET PARAMETERS############
    import argparse
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
             description="""
       This module computes anharmonic corrections to the projected
       frequencies produced during an EStokTP 1D or MD torsional scan.  

       Requirements: 
       In addition to both the projected frequency and unprojected frequency files that 
       EStokTP puts in me_files, it requires EITHER a g09 anharmonic logfile OR for g09 
       to be available so that this module can execute a g09 anharmonic computation 
       written using an optimization logfile (usually taken from geoms/reac1_l1.log)
       """)

    parser.add_argument('-n',         '--natoms',type=int,help = 'number of atoms in the molecule. Required.',                              required=True)
    parser.add_argument('-a',      '--anharmlog',type=str,help = 'location of g09 anharmonic logfile IF unavailable, use next 3 options',   default='anharm.log')
    parser.add_argument('-l',        '--logfile',type=str,help = 'path to  optimization logfile (required if no g09 anharmfile available)', default='geoms/reac1_l1.log')
    parser.add_argument('-w',     '--writegauss',type=str,help = 'if true will write gaussian anharmonic input file',                       default='false')
    parser.add_argument('-r',       '--rungauss',type=str,help = 'if true will execute guassian anharmonic computation',                    default='false')
    parser.add_argument('-freq',    '--freqfile',type=str,help = 'path to estoktp UNprojected frequency file found in me_files',            default='me_files/reac1_fr.me')
    parser.add_argument('-unfreq','--unprojfreq',type=str,help = 'path to estoktp   projected frequency file foudn in me_files',            default='me_files/reac1_unprfr.me')
    parser.add_argument('-x',  '--computeanharm',type=str,help = 'specify false to avoid computing anharmonic correction',                  default='true')
    parser.add_argument('-N',           '--node',type=str,help = 'which blues node to run on (e.g. b447). Required.',                       required=True)
    ##########################

    args      = parser.parse_args()
    main(args)

