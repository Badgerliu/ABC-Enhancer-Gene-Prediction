import os
import pandas
import pickle
#from intervaltree import IntervalTree, Interval
#import pysam
import numpy as np
import pandas as pd
import re
import seaborn as sns
from subprocess import check_call
import sys
import pyranges as pr

# setting this to raise makes sure that any dangerous assignments to pandas
# dataframe slices/subsets error rather than warn
pandas.set_option('mode.chained_assignment', 'raise')

# Generates QC Prediction Metrics: 
def GrabQCMetrics(prediction_df, outdir ):
    GeneCounts = prediction_df.groupby(['TargetGene']).size()
    GeneCounts.to_csv(os.path.join(outdir,"EnhancerPerGene.txt"), sep="\t")

    GeneMean = prediction_df.groupby(['TargetGene']).size().mean()
    GeneStdev = prediction_df.groupby(['TargetGene']).size().std()
    # Grab Number of genes per enhancers
    num_enhancers = prediction_df[['chr', 'start', 'end']].groupby(['chr', 'start', 'end']).size()
    num_enhancers.to_csv(os.path.join(outdir,"GenesPerEnhancer.txt"), sep="\t")
    mean_genes_per_enhancer = prediction_df[['chr', 'start', 'end']].groupby(['chr', 'start', 'end']).size().mean()
    stdev_genes_per_enhancer = prediction_df[['chr', 'start', 'end']].groupby(['chr', 'start', 'end']).size().std()

    # Grab Number of Enhancer-Gene Pairs Per Chromsome
    enhancergeneperchrom = prediction_df.groupby(['chr']).size()
    enhancergeneperchrom.to_csv(os.path.join(outdir, "EnhancerGenePairsPerChrom.txt"), sep="\t")

    # Enhancer-Gene Distancee
    midpoint = prediction_df['start'] + (prediction_df['end'] - prediction_df['start'])*0.5
    enhancer_gene_distance = np.absolute(prediction_df['TargetGeneTSS'] - midpoint)
    # Plot Distributions and save as png
    PlotDistribution(num_enhancers, "NumberOfGenesPerEnhancer", outdir)
    PlotDistribution(GeneCounts, "NumberOfEnhancersPerGene", outdir)
    PlotDistribution(enhancergeneperchrom, "EnhancersPerChromosome", outdir)
    PlotDistribution(enhancer_gene_distance, "EnhancerGeneDistance", outdir)

    with open(os.path.join(outdir, "QCSummary.txt"), "w") as f:
        f.write("Average Number of Enhancers per Gene: ")
        f.write(str(GeneMean))
        f.write("\n")
        f.write("Standard Deviation of Enhancers per Gene:")
        f.write(str(GeneStdev))
        f.write("\n")
        f.write("Average Number of Genes linked to an Enhancer:")
        f.write(str(mean_genes_per_enhancer))
        f.write("\n")
        f.write("Standard Deviation of Genes linked to an Enhancer:")
        f.write(str(stdev_genes_per_enhancer))
        f.write("\n")
        f.write("Mean Enhancer-Gene Distance:")
        f.write(str(distance.mean()))
        f.write("\n")
        f.write("Standard Deviation of Enhancer-Gene Distance:")
        f.write(str(distance.std()))
        f.write("\n")
        f.close()

# Generates peak file metrics 
def PeakFileQC(peakfile, outdir):
    if peakfile.endswith(".gz"):
        peaks = pd.read_csv(peakfile, compression="gzip", sep="\t", header=None)
    else:
        peaks = pd.read_csv(peakfile, sep="\t", header=None)
    peaks['dist'] = peaks[2]-peaks[1]
    peaks_array = list(peaks['dist'])
    PlotDistribution(peaks_array, "WidthOfPeaks", outdir)

    with open(os.path.join(outdir, "PeakFileQCSummary.txt"),"w") as f:
        f.write(str(peakfile))
        f.write("\n")
        f.write("Number of peaks: ")
        f.write(str(len(peaks['dist'])))
        f.write("\n")
        f.write("Max width of peak: ")
        f.write(str(max(peaks['dist'])))
        f.write("\n")
        f.write("Mean and Stdev width of peaks: ")
        f.write(str(peaks['dist'].mean()))
        f.write("\t")
        f.write(str(peaks['dist'].std()))
        f.write("\n")
        f.close()
# Plots and saves a distribution as *.png
def PlotDistribution(array, title, outdir):
    ax = sns.distplot(array)
    ax.set_title(title)
    ax.set_ylabel('Estimated PDF of distribution')
    ax.set_xlabel('Counts')
    fig = ax.get_figure()
    outfile = os.path.join(outdir, str(title)+".pdf")
    fig.savefig(outfile, format='pdf')

def run_command(command, **args):
    print("Running command: " + command)
    return check_call(command, shell=True, **args)

def write_connections_bedpe_format(pred, outfile, score_column):
    #Output a 2d annotation file with EP connections in bedpe format for loading into IGV
    pred = pred.drop_duplicates()

    towrite = pandas.DataFrame()

    towrite["chr1"] = pred["chr"]
    towrite["x1"] = pred['start']
    towrite["x2"] = pred['end']
    towrite["chr2"] = pred["chr"]
    towrite["y1"] = pred["TargetGeneTSS"]
    towrite["y2"] = pred["TargetGeneTSS"]
    towrite["name"] = pred["TargetGene"] + "_" + pred["name"]
    towrite["score"] = pred[score_column]
    towrite["strand1"] = "."
    towrite["strand2"] = "."

    towrite.to_csv(outfile, header=False, index=False, sep = "\t")

def determine_expressed_genes(genes, expression_cutoff, activity_quantile_cutoff):
    #Evaluate whether a gene should be considered 'expressed' so that it runs through the model

    #A gene is runnable if:
    #It is expressed OR (there is no expression AND its promoter has high activity)

    genes['isExpressed'] = np.logical_or(genes.Expression >= expression_cutoff, np.logical_and(np.isnan(genes.Expression), genes.PromoterActivityQuantile >= activity_quantile_cutoff))

    return(genes)

def write_params(args, file):
    with open(file, 'w') as outfile:
        for arg in vars(args):
            outfile.write(arg + " " + str(getattr(args, arg)) + "\n")

def df_to_pyranges(df, start_col='start', end_col='end', chr_col='chr', start_slop=0, end_slop=0):
    df['Chromosome'] = df[chr_col]
    df['Start'] = df[start_col] - start_slop
    df['End'] = df[end_col] + end_slop

    return(pr.PyRanges(df))

# def write_scores(outdir, gene, enhancers):
#     outfile = get_score_filename(gene)
#     enhancers.to_csv(os.path.join(outdir, outfile), sep="\t", index=False, compression="gzip", float_format="%.6f", na_rep="NaN")

# def read_genes(filename):
#     genes = pandas.read_table(filename)

#     #Deduplicate genes.
#     gene_cols = ['chr','tss','name','Expression','PromoterActivityQuantile']
#     genes = genes[gene_cols]
#     genes.drop_duplicates(inplace=True)

#     return genes
    
# def get_score_filename(gene, outdir = None):
#     out_name = get_gene_name(gene)
#     outfile = "{}_{}_{}.prediction.txt.gz".format(out_name, gene.chr, int(gene.tss))
#     if outdir is not None:
#         outfile = os.path.join(outdir, outfile)
#     return outfile

# def get_gene_name(gene):
#     try:
#         out_name = gene['name'] #if ('symbol' not in gene.keys() or gene.isnull().symbol) else gene['symbol']
#     except:
#         out_name = "_UNK"
#     return str(out_name)

# class GenomicRangesIntervalTree(object):
#     def __init__(self, filename, slop=0, isBed=False):
#         if isBed:
#             self.ranges = pandas.read_table(filename, header=None, names=['chr', 'start', 'end', 'Score'])
#         elif isinstance(filename, pandas.DataFrame):
#             self.ranges = filename
#         else:
#             self.ranges = pandas.read_table(filename)

#         self.ranges['start'] = self.ranges['start'] - slop
#         self.ranges['end'] = self.ranges['end'] + slop
#         self.ranges['end'] = [ max(x,y) for x,y in zip(self.ranges['start']+1,self.ranges['end']) ]
#         assert(pandas.DataFrame.all(self.ranges.start <= self.ranges.end))
        
#         self.intervals = {}
#         for chr, chrdata in self.ranges.groupby('chr'):
#             self.intervals[chr] = IntervalTree.from_tuples(zip(chrdata.start,
#                                                                chrdata.end,
#                                                                chrdata.index))

#     def within_range(self, chr, start, end):
#         # Returns empty data frame (0 rows) if there is no overlap
#         if start == end:   ## Interval search doesn't like having start and end equal
#             end = end + 1
#         result = self.ranges.iloc[[], :].copy()
#         if chr in self.intervals:
#             overlaps = self.intervals[chr][start:end]
#             indices = [idx for l, h, idx in overlaps]
#             result = self.ranges.iloc[indices, :].copy()
#         return result

#     def overlaps(self, chr, start, end):
#         locs = self.intervals[chr].overlaps()

#     def __getitem__(self, idx):
#         return self.ranges[idx]

# def read_enhancers(filename):
#     return GenomicRangesIntervalTree(filename)

# class DataCache(object):
#     def __init__(self, directory):
#         os.makedirs(directory, exist_ok=True)
#         self.directory = directory

#     def __contains__(self, filename):
#         cache_name = os.path.join(self.directory, filename.replace(os.sep, '__'))
#         if os.path.exists(cache_name) and (os.path.getctime(cache_name) > os.path.getctime(filename)):
#             return True
#         return False

#     def __getitem__(self, filename):
#         cache_name = os.path.join(self.directory, filename.replace(os.sep, '__'))
#         if os.path.exists(cache_name) and (os.path.getctime(cache_name) > os.path.getctime(filename)):
#             with open(cache_name, "rb") as f:
#                 return pickle.load(f)
#         raise KeyError

#     def __setitem__(self, filename, value):
#         cache_name = os.path.join(self.directory, filename.replace(os.sep, '__'))
#         with open(cache_name, "wb") as f:
#             pickle.dump(value, f, protocol=pickle.HIGHEST_PROTOCOL)
