#!/usr/bin/env python

import sys
import string
import gzip
import time
from operator import itemgetter
from optparse import OptionParser
import argparse, sys , re
from argparse import RawTextHelpFormatter

__author__ = "Abhijit Badve (abadve@genome.wustl.edu)"
__version__ = "$Revision: 0.0.1 $"
___date__ = "$Date: 2015-09-02 12:00 $"

def get_args():
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter, description="\
varLookup\n\
author: " + __author__ + "\n\
version: " + __version__ + "\n\
description: Look for variants common between two bedpe files")
    parser.add_argument('-d', '--distance',
                        metavar='INT', type=int,
                        dest='max_distance',
                        required=False,
                        default=50,
                        help='max separation distance (bp) of adjacent loci between bedpe files [50]')
    parser.add_argument("-a", "--aFile", 
                        dest="aFile",
                        metavar="FILE",
                        required=False,
                        help="Pruned merged bedpe (A file) or standard input (-a stdin). ")
    parser.add_argument("-b", "--bFile", 
                        dest="bFile", 
                        metavar="FILE",
                        required=False,
                        help="Pruned merged bedpe (B file) (-b stdin). For prunning use -- ClusterBedpe.py")
    parser.add_argument("-c", "--cohort", 
                        metavar='string', type=str,
                        dest='cohort_name',
                        required=False,
                        default=None,
                        help="Cohort name to add information of matching variants (default:bFile)")                    
    parser.add_argument('-o', '--output', 
                        type=argparse.FileType('w'), 
                        default=sys.stdout, help='Output BEDPE to write (default: stdout)')
                        
    
    args = parser.parse_args()
    # if no input, check if part of pipe and if so, read stdin.
    if args.aFile == None:
        if sys.stdin.isatty():
            parser.print_help()
            exit(1)
        else:
            args.aFile = sys.stdin

    # send back the user input
    return args
class Bedpe(object):
    def __init__(self, line):
        v = line.strip().split("\t")
        self.chrom_a = v[0]
        self.start_a = int(v[1])
        self.end_a = int(v[2])
        self.chrom_b = v[3]
        self.start_b = int(v[4])
        self.end_b = int(v[5])
        self.id = v[6]
        self.qual = v[7]
        self.info = v[12]
        self.af=filter(lambda x: x if x.startswith('AF=') else None, self.info.split(";"))
        #print self.af
        self.cohort_vars = dict()
        if self.af is not None and len(self.af) == 1:
            self.af=''.join(self.af).replace('AF=','')
        else: 
            print "No allele frequency for variants found. Input a valid file"
            sys.exit(0)
        
        self.sv_event=filter(lambda x: x if x.startswith('SVTYPE=') else None, self.info.split(";"))
        if self.sv_event is not None and len(self.sv_event) == 1:
            self.sv_event=''.join(self.sv_event).replace('SVTYPE=','')
        else:
            print "No svtype field found. Input a valid file"
            sys.exit(0)
        self.filter = v[11]
        try:
            self.strand_a = v[8]
            self.strand_b = v[9]
        except IndexError:
            self.strand_a = ''
            self.strand_b = ''
        self.vec = '\t'.join(v[13:])
    def get_var_string(self,cohort_name):
        if len(self.cohort_vars)>0:
            self.info = self.info + ';' + cohort_name + '_AF=' + ','.join([value for (key, value) in sorted(self.cohort_vars.items(), key=itemgetter(1),reverse=True)])
            self.info = self.info + ';' + cohort_name + '_VarID=' + ','.join([key for (key, value) in sorted(self.cohort_vars.items(), key=itemgetter(1),reverse=True)])
        else:
            self.info = self.info + ';' + cohort_name + '_AF=' + str(0)
            self.info = self.info + ';' + cohort_name + '_VarID=' + 'NONE'
        return '\t'.join([self.chrom_a,str(self.start_a),str(self.end_a),\
                        self.chrom_b,str(self.start_b),str(self.end_b),\
                        self.id,self.qual,self.strand_a,self.strand_b,\
                        self.sv_event,self.filter,self.info,self.vec]) + '\n'
class Header(object):
    def __init__(self):
        self.file_format="BEDPE"
        self.reference=''
        self.sample_list=[]
        self.info_list = []
        self.format_list = []
        self.alt_list = []
        self.add_format('GT', 1, 'String', 'Genotype')
    def add_header(self,line):
        if line.split('=')[0] == '##fileformat':
                self.file_format = line.rstrip().split('=')[1]
        elif line.split('=')[0] == '##reference':
            self.reference = line.rstrip().split('=')[1]
        elif line.split('=')[0] == '##INFO':
            a = line[line.find('<')+1:line.find('>')]
            r = re.compile(r'(?:[^,\"]|\"[^\"]*\")+')
            self.add_info(*[b.split('=')[1] for b in r.findall(a)])
        elif line.split('=')[0] == '##ALT':
            a = line[line.find('<')+1:line.find('>')]
            r = re.compile(r'(?:[^,\"]|\"[^\"]*\")+')
            self.add_alt(*[b.split('=')[1] for b in r.findall(a)])
        elif line.split('=')[0] == '##FORMAT':
            a = line[line.find('<')+1:line.find('>')]
            r = re.compile(r'(?:[^,\"]|\"[^\"]*\")+')
            self.add_format(*[b.split('=')[1] for b in r.findall(a)])
        elif line[0] == '#' and line[1] != '#':
            self.sample_list = line.rstrip().split('\t')[15:]
    # return the BEDPE header
    def get_header(self):
        if len(self.sample_list) > 0:
            header_string = '\n'.join(['##fileformat=' + self.file_format,
                                '##fileDate=' + time.strftime('%Y%m%d'),
                                '##reference=' + self.reference] + \
                                 [i.hstring for i in self.info_list] + \
                                 [a.hstring for a in self.alt_list] + \
                                 [f.hstring for f in self.format_list] + \
                                 ['\t'.join(['#CHROM_A',
                                               'START_A',
                                               'END_A',
                                               'CHROM_B',
                                               'START_B',
                                               'END_B',
                                               'ID',
                                               'QUAL',
                                               'STRAND_A',
                                               'STRAND_B',
                                               'TYPE',
                                               'FILTER',
                                               'INFO_A',
                                               'INFO_B',
                                               'FORMAT'] +
                                               self.sample_list
                                              )]) + '\n'
        else:
            header_string = '\n'.join(['##fileformat=' + self.file_format,
                                '##fileDate=' + time.strftime('%Y%m%d'),
                                '##reference=' + self.reference] + \
                                 [i.hstring for i in self.info_list] + \
                                 [a.hstring for a in self.alt_list] + \
                                 [f.hstring for f in self.format_list] + \
                                 ['\t'.join(['#CHROM_A',
                                               'START_A',
                                               'END_A',
                                               'CHROM_B',
                                               'START_B',
                                               'END_B',
                                               'ID',
                                               'QUAL',
                                               'STRAND_A',
                                               'STRAND_B',
                                               'TYPE',
                                               'FILTER',
                                               'INFO_A',
                                               'INFO_B',
                                               'FORMAT']
                                              )]) + '\n'              
        return header_string
    def add_info(self, id, number, type, desc):
        if id not in [i.id for i in self.info_list]:
            inf = Info(id, number, type, desc)
            self.info_list.append(inf)

    def add_alt(self, id, desc):
        if id not in [a.id for a in self.alt_list]:
            alt = Alt(id, desc)
            self.alt_list.append(alt)

    def add_format(self, id, number, type, desc):
        if id not in [f.id for f in self.format_list]:
            fmt = Format(id, number, type, desc)
            self.format_list.append(fmt)

    def add_sample(self, name):
        self.sample_list.append(name)
        
class Info(object):
    def __init__(self, id, number, type, desc):
        self.id = str(id)
        self.number = str(number)
        self.type = str(type)
        self.desc = str(desc)
        # strip the double quotes around the string if present
        if self.desc.startswith('"') and self.desc.endswith('"'):
            self.desc = self.desc[1:-1]
        self.hstring = '##INFO=<ID=' + self.id + ',Number=' + self.number + ',Type=' + self.type + ',Description=\"' + self.desc + '\">'

class Alt(object):
    def __init__(self, id, desc):
        self.id = str(id)
        self.desc = str(desc)
        # strip the double quotes around the string if present
        if self.desc.startswith('"') and self.desc.endswith('"'):
            self.desc = self.desc[1:-1]
        self.hstring = '##ALT=<ID=' + self.id + ',Description=\"' + self.desc + '\">'

class Format(object):
    def __init__(self, id, number, type, desc):
        self.id = str(id)
        self.number = str(number)
        self.type = str(type)
        self.desc = str(desc)
        # strip the double quotes around the string if present
        if self.desc.startswith('"') and self.desc.endswith('"'):
            self.desc = self.desc[1:-1]
        self.hstring = '##FORMAT=<ID=' + self.id + ',Number=' + self.number + ',Type=' + self.type + ',Description=\"' + self.desc + '\">'

def add(a_bedpe,b_bedpe,max_distance):
    if a_bedpe.sv_event ==  b_bedpe.sv_event:
        if (a_bedpe.strand_a != b_bedpe.strand_a
            or a_bedpe.strand_b != b_bedpe.strand_b):
            return False

        if (a_bedpe.chrom_a != b_bedpe.chrom_a
            or a_bedpe.start_a - max_distance > b_bedpe.end_a
            or a_bedpe.end_a + max_distance < b_bedpe.start_a):
            return False

        if (a_bedpe.chrom_b != b_bedpe.chrom_b
            or a_bedpe.start_b - max_distance > b_bedpe.end_b
            or a_bedpe.end_b + max_distance < b_bedpe.start_b):
            return False
        else:
            a_bedpe.cohort_vars[b_bedpe.id]=b_bedpe.af
            return True
    else:
        return False
def varLookup(aFile, bFile,bedpe_out, max_distance,pass_prefix,cohort_name):
    bList = list()
    headerObj=Header()
    if cohort_name is None:
        cohort_name=str(str(bFile).split('/')[-1])
        
    if bFile == "stdin":
        bData = sys.stdin
    elif bFile.endswith('.gz'):
        bData = gzip.open(bFile, 'rb')
    else:
        bData = open(bFile, 'r')
    for bLine in bData:
        if bLine.startswith(pass_prefix):
            continue
        bList.append(Bedpe(bLine))
    
    if aFile == "stdin":
        aData = sys.stdin
    elif aFile.endswith('.gz'):
        aData = gzip.open(aFile, 'rb')
    else:
        aData = open(aFile, 'r')
    in_header=True    
    for aLine in aData:
        if pass_prefix is not None and aLine.startswith(pass_prefix):
            headerObj.add_header(aLine)
            continue
        else:
            if in_header == True:
                headerObj.add_info(cohort_name + '_AF', '.', 'Float', 'Allele frequency(ies) for matching variants found in the ' + cohort_name + ' vcf' + ' (' + str(str(bFile).split('/')[-1]) + ')' )
                headerObj.add_info(cohort_name + '_VarID', '.', 'Integer', 'List of Variant ID(s) for matching variants found in the ' + cohort_name + ' vcf' + ' (' + str(str(bFile).split('/')[-1]) + ')' )
                bedpe_out.write(str(headerObj.get_header()))
                in_header=False
            a = Bedpe(aLine)
            for b in bList:
                add(a,b,max_distance)
            bedpe_out.write(a.get_var_string(cohort_name))

def main():
    pass_prefix = "#"
    # parse the command line args
    args = get_args()
    if args.aFile is None:
       parser.print_help()
       print
    else:
        try:
        	varLookup(args.aFile, args.bFile,args.output, args.max_distance,pass_prefix,args.cohort_name)
        except IOError as err:
        	sys.stderr.write("IOError " + str(err) + "\n");
    	return

if __name__ == "__main__":
	try:
		main()
        except IOError, e:
		if e.errno != 32:  # ignore SIGPIPE
			raise 
