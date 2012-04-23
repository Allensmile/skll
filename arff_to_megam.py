#!/usr/bin/env python

# Script that converts ARFF files to MegaM format

# Author: Dan Blanchard, dblanchard@ets.org, Sep 2011

import argparse
import csv
import random
import re
import sys


# Globals
args = None


def parse_num_list(num_string):
    '''
        Convert a string representing a range of numbers to a list of integers.
    '''
    range_list = []
    if (num_string != '') and (not re.match(r'^(\d+(-\d+)?,)*\d+(-\d+)?$', num_string)):
        raise argparse.ArgumentTypeError("'" + num_string + "' is not a range of numbers. Expected forms are '8-15', '4,8,15,16,23,42', or '3-16,42'.")
    for rng in num_string.split(','):
        if rng.count('-'):
            split_range = [int(x) for x in rng.split('-')]
            split_range[1] += 1
            range_list.extend(range(*split_range))
        else:
            range_list.append(int(rng))
    return range_list


def split_with_quotes(s, delimiter=' ', quotechar="'", escapechar='\\'):
    '''
        A replacement for string.split that won't split delimiters enclosed in quotes.
    '''
    return csv.reader([s], delimiter=delimiter, quotechar=quotechar, escapechar=escapechar).next()


def nominal_to_numeric_dict(nominal_list):
    '''
        Create a dict for a list of nominal values that will convert the strings to integers
    '''
    num_dict = dict()
    for i in xrange(len(nominal_list)):
        num_dict[nominal_list[i]] = i
    return num_dict


def sanitize_name(feature_name):
    '''
        Replaces bad characters in feature names.
    '''
    return feature_name.replace(" ", "_").replace("#", "HASH")


def print_instance(instance, nominal_dict, attr_list, suffix=None):
    # Loop through all attributes in instance set.
    for i in xrange(len(instance)):
        # Skip over the class feature
        if i != args.classindex:
            # Check if this a feature we want to keep
            if ((not args.features) or ((i + 1) in args.features)) and ((i + 1) not in args.superclasses):
                clean_name = sanitize_name(attr_list[i][0] if suffix is None else "F{}{}".format(i + 1, suffix))
                # Feature is numeric
                if attr_list[i][1] == 1:
                    # Only print feature if it's not zero to save space
                    if float(instance[i]):
                        # Check if we're supposed to convert the feature to binary
                        if (args.binary and ((args.binary == [0]) or ((i + 1) in args.binary))):
                            print clean_name, int(bool(float(instance[i]))),
                            if args.doubleup:
                                print clean_name, instance[i],
                        else:
                            print clean_name, instance[i],
                # Feature is nominal
                elif i in nominal_dict:
                    print clean_name, nominal_dict[i][instance[i]],
                # Feature is string, so ignore it
                elif args.verbose:
                    print >> sys.stderr, clean_name, instance[i],
            elif args.verbose:
                print >> sys.stderr, clean_name, instance[i],
    if args.verbose:
        print >> sys.stderr


def process_set(inst_set, nominal_dict, attr_list, inst_str_list):
    '''
        Process an instance set and output MegaM-style instances
    '''
    for inst_index in inst_set:
        instance = split_with_quotes(inst_str_list[inst_index], quotechar=args.quotechar, delimiter=',')  # Split on demand to save tons of memory
        print (sanitize_name(instance[args.classindex]) if args.namedclasses else str(nominal_dict[args.classindex][instance[args.classindex]])) + "\t",
        # Use explicit output format if superclasses are specified
        if args.superclasses:
            for class_name in attr_list[args.classindex][2]:
                print "#",
                print_instance(instance, nominal_dict, attr_list, suffix=" " + class_name)
                for superclass_feat in args.superclasses:
                    print_instance(instance, nominal_dict, attr_list, suffix=" {} {}".format(attr_list[superclass_feat - 1][0], instance[superclass_feat - 1]))
        # Otherwise use implicit output format
        else:
            print_instance(instance, nominal_dict, attr_list)
        print


if __name__ == '__main__':
    # Get command line arguments
    parser = argparse.ArgumentParser(description="Takes an ARFF file an outputs a MegaM-compatible file to be run with the '-fvals' switch." +
                                                 " Assumes last field is class. Ignores any relational, string, or date fields. Automatically converts nominals" +
                                                 " to numerals.",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('infile', help='ARFF input file', type=argparse.FileType('r'), default='-', nargs='?')
    parser.add_argument('-b', '--binary', help='Converts the specified range of numeric features to presence/absence binary features. Features are numbered ' +
                                               'starting from 1, and if 0 is specified with this flag, all numeric features are converted. Note: Any string ' +
                                               'features within the specified range are just ignored.', type=parse_num_list)
    parser.add_argument('--doubleup', help='Keep both the binary and numeric versions of any feature numeric feature you convert to binary.', action='store_true')
    parser.add_argument('-c', '--classindex', help='Index of feature that is the class. Numbering starts at 1 like --features. Supports negative numbers (i.e., ' +
                                                   '-1 is the last feature).',
                        type=int, default=-1)
    parser.add_argument('-d', '--dev', help='Number of instances per class to reserve for development.', type=int, default=0)
    parser.add_argument('-f', '--features', help='Only keep the specified range of features in the MegaM output. Features are numbered starting from 1.',
                        type=parse_num_list)
    parser.add_argument('-m', '--max', help='Maximum number of instances to use for training for each class.', type=int, default=0)
    parser.add_argument('-n', '--namedclasses', help='Keep class names in MegaM file instead of converting the nomimal field to numeric.', action='store_true')
    parser.add_argument('-q', '--quotechar', help='Character to use for quoting strings in attribute names.', default="'")
    parser.add_argument('-r', '--randomize', help='Randomly shuffle the instances before splitting into training, dev, and test sets.', action='store_true')
    parser.add_argument('-s', '--superclasses', help='List of features that are super-classes of the classes we want to have MegaM predict. If specified, the ' +
                                                     'MegaM "explicit" output format will be used.',
                        type=parse_num_list, default=[])
    parser.add_argument('-t', '--test', help='Number of instances per class to reserve for testing.', type=int, default=0)
    parser.add_argument('-v', '--verbose', help='Print out fields that were not added output to MegaM file on STDERR.', action='store_true')
    args = parser.parse_args()

    # Check for valid classindex
    if args.classindex == 0:
        raise argparse.ArgumentTypeError("0 is not a valid value for --classindex.  Feature numbering starts at 1 (although --classindex can also be negative).")

    # Process ARFF header
    attr_list = []
    relation = ''
    for line in args.infile:
        if line.strip():
            # Split the line using CSV reader because it can handle quoted delimiters.
            split_header = split_with_quotes(line, quotechar=args.quotechar)
            row_type = split_header[0].lower()
            if row_type == '@attribute':
                # Nominal
                if split_header[2][0] == '{':
                    attr_list.append([split_header[1], 2, [x.strip() for x in split_with_quotes(' '.join(split_header[2:]).strip('{}'),
                                                                                            quotechar=args.quotechar, delimiter=',')]])
                # Numeric or String
                else:
                    attr_list.append([split_header[1], int(split_header[2] == 'numeric'), []])
            elif row_type == '@data':
                break
            elif row_type == '@relation':
                relation = split_header[1]

    # Shift classindex so that it matches actual array indexing
    if args.classindex > 0:
        args.classindex -= 1
    else:
        args.classindex += len(attr_list)

    # Convert nominal features to numeric
    nominal_dict = dict([(i, nominal_to_numeric_dict(attr_list[i][2])) for i in xrange(len(attr_list)) if attr_list[i][1] == 2])
    class_list = attr_list[args.classindex][2]
    class_dict = nominal_dict[args.classindex]

    # Initialize dev, test, and train sets
    dev_sets = [set() for x in class_list]
    test_sets = [set() for x in class_list]
    train_sets = [set() for x in class_list]

    # Process data instances
    inst_str_list = [line.strip() for line in args.infile]  # Picks up on line after @data because of break in loop that processes header
    args.infile.close()

    # Randomize if asked
    if args.randomize:
        random.shuffle(inst_str_list)

    # Split instance list into dev, test, and training sets
    for i, inst_str in enumerate(inst_str_list):
        instance = split_with_quotes(inst_str, quotechar=args.quotechar, delimiter=',')
        if len(dev_sets[class_dict[instance[args.classindex]]]) < args.dev:
            dev_sets[class_dict[instance[args.classindex]]].add(i)
        elif len(test_sets[class_dict[instance[args.classindex]]]) < args.test:
            test_sets[class_dict[instance[args.classindex]]].add(i)
        elif (not args.max) or (len(train_sets[class_dict[instance[args.classindex]]]) < args.max):
            train_sets[class_dict[instance[args.classindex]]].add(i)

    # Process each training set
    for inst_set in train_sets:
        process_set(inst_set, nominal_dict, attr_list, inst_str_list)

    # Process each dev set
    if args.dev:
        print "DEV"
        for inst_set in dev_sets:
            process_set(inst_set, nominal_dict, attr_list, inst_str_list)

    # Process each test set
    if args.test:
        print "TEST"
        for inst_set in test_sets:
            process_set(inst_set, nominal_dict, attr_list, inst_str_list)
