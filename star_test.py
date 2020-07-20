"""
testing rgToolFactoryMulIn
make a count matrix from star junction files

SJ.out.tab - high confidence collapsed splice junctions in tab-delimited format. Only junctions supported by
uniquely mapping reads are reported.
Column 1: chromosome
Column 2: first base of the intron (1-based)
Column 3: last base of the intron (1-based)
Column 4: strand
Column 5: intron motif: 0: non-canonical; 1: GT/AG, 2: CT/AC, 3: GC/AG, 4: CT/GC, 5: AT/AC, 6: GT/AT
Column 6: 0: unannotated, 1: annotated (only if splice junctions database is used)
Column 7: number of uniquely mapping reads crossing the junction
Column 8: number of multi-mapping reads crossing the junction
Column 9: maximum spliced alignment overhang

"""
import sys
outf = sys.argv[1]
infs = sys.argv[2:]
ninfs = len(infs)
dres = {}
head = ['contig',]
for i,f in enumerate(infs):
    fnum = i+1
    if f.find(',') <> -1:
       fin,fname = f.split(',')
    else:
       fin = f
       fname = f
    head.append(fname)
    dat = open(fin,'r').readlines()
    dat = [x.strip().split('\t') for x in dat]
    dat = [x for x in dat if len(x) >= 8]
    for row in dat:
        contig = 'chr%s:%s-%s' % (row[0],row[1],row[2])
        ureads = int(row[6])
        if ureads > 0:
            dres.setdefault(contig,[0 for x in range(ninfs)]) # all zero counts
            dres[contig][fnum] = ureads
dk = dres.keys()
dk.sort()
o = open(outf,'w')
o.write('\t'.join(head))
o.write('\n')
for k in dk:
    row = dres[k]
    row = ['%d' % x for x in row] # to strings
    o.write('\t'.join(row))
    o.write('\n')
o.close()
